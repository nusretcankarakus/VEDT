"""Actual fio on newly allocated regular files; never opens a physical disk."""
import os
import shutil
import sys
import pytest
from disktest import raw
from disktest.safety import Identity

pytestmark = pytest.mark.skipif(sys.platform != 'linux' or not shutil.which('fio'), reason='Linux fio required')

@pytest.mark.parametrize('tail,corrupt', [(0,False),(512,False),(4096,False),(512,True)])
def test_full_capacity_large_io_and_tail_with_real_fio(tmp_path, monkeypatch, tail, corrupt):
    size = 64*1024**2 + tail
    target = tmp_path/'owned-test-file.bin'
    with target.open('xb') as stream:stream.truncate(size)
    class FileDevice:
        logical_sector = 512
        def __init__(self, *args, **kwargs):self.path=target
        def __enter__(self):self.fd=os.open(target,os.O_RDWR);return self
        def __exit__(self,*args):os.close(self.fd)
        def boundary(self):pass
        def check_fd(self):pass
        def stats(self):return (0,0)
        def native_ids(self):return {}
    monkeypatch.setattr(raw,'PinnedDevice',FileDevice)
    monkeypatch.setattr(raw,'persistent_reports',lambda _:None)
    monkeypatch.setattr(raw,'read_smart',lambda *args,**kwargs:{'health':'PASS','temperature_c':None,'raw':{}})
    real_popen=raw.subprocess.Popen
    injected=False
    def launch(command,*args,**kwargs):
        nonlocal injected
        if corrupt and '--verify_only=1' in command and not injected:
            with target.open('r+b',buffering=0) as stream:
                stream.seek(size-1);value=stream.read(1);stream.seek(size-1)
                stream.write(bytes([value[0]^255]));os.fsync(stream.fileno())
            injected=True
        return real_popen(command,*args,**kwargs)
    monkeypatch.setattr(raw.subprocess,'Popen',launch)
    identity=Identity('OWNED-FILE','Test file',size,'test-wwn')
    events=[]
    result=raw.run_raw(raw.RawSettings(identity,allow_destroy=True,timeout_seconds=120),identity.serial,tmp_path,events.append,accept_data_loss=True)
    assert all(row['status']=='PENDING' for row in events[0]['stage_states'])
    if corrupt:
        assert injected and result['status']=='FAIL'
        assert result['full_capacity_verified'] is False
        assert result['error']['kind']=='FioDataMismatch'
    else:
        assert result['error'] is None, result['error']
        assert len(result['stages'])==6
        assert all(s['status']=='PASS' for s in result['stages'])
        assert all(result['stages'][i]['bytes']==size for i in (2,3,5))
        assert result['full_capacity_verified'] is True
        writes=[e for e in events if e.get('stage_index')==2]
        assert writes and all(a['stage_elapsed_seconds']<=b['stage_elapsed_seconds'] for a,b in zip(writes,writes[1:]))
        if tail:
            assert any(e['stage_states'][2]['status']=='RUNNING' and e['stage_bytes']==64*1024**2 for e in writes)
        for item in result['fio_results']:
            if item['stage'] in [result['stages'][i]['name'] for i in (2,3,5)]:
                assert '--ioengine=libaio' in item['argv']
