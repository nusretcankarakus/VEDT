from disktest.progress import Progress, STAGES
from disktest.framebuffer import Fixed, Variable, pixel_mode
import pytest


def rows_before_write():
    return [{'name': STAGES[i], 'status': 'PASS', 'bytes': size, 'seconds': 1}
            for i, size in enumerate((32*1048576, 4194304))]


def test_all_six_steps_pending_before_any_io():
    state = Progress(10**12, 4096).snapshot([], 5)
    assert len(state['stage_states']) == 6
    assert all(s['status'] == 'PENDING' for s in state['stage_states'])
    assert state['overall_eta_seconds'] is None


def test_stage_and_whole_test_eta_are_different_and_weighted_by_work():
    tracker = Progress(10**12, 4096)
    rows = rows_before_write()+[{'name': STAGES[2], 'status':'RUNNING', 'bytes':0, 'seconds':0}]
    tracker.snapshot(rows, 100, STAGES[2], 100*10**9, 98)
    state = tracker.snapshot(rows, 110, STAGES[2], 110*10**9, 108)
    assert state['stage_elapsed_seconds'] == 108
    assert state['elapsed_seconds'] == 110
    assert state['stage_eta_seconds'] == pytest.approx(890)
    assert state['overall_eta_seconds'] > state['stage_eta_seconds']+1900
    assert 3 < state['overall_percent'] < 4  # Not 2.11 / 6 phases.
    assert state['stage_states'][3]['status']=='PENDING'
    assert state['overall_eta_provisional']


def test_tail_does_not_reset_stage_clock_or_mark_pass_prematurely():
    tracker = Progress(64*1048576+512, 256)
    rows = rows_before_write()+[{'name':STAGES[2], 'status':'RUNNING', 'bytes':64*1048576, 'seconds':5}]
    state = tracker.snapshot(rows, 10, STAGES[2], 64*1048576, 6)
    assert state['stage_states'][2]['status']=='RUNNING'
    assert state['stage_states'][2]['seconds']==6
    assert state['percent'] < 100


def test_failure_never_marks_remaining_steps_complete_or_reports_eta_zero():
    tracker = Progress(10**12, 256)
    rows = rows_before_write()+[{'name':STAGES[2], 'status':'FAIL', 'bytes':100, 'seconds':10}]
    state = tracker.snapshot(rows, 15, STAGES[2], 100, 10, final_status='FAIL')
    assert state['stage_eta_seconds'] is None and state['overall_eta_seconds'] is None
    assert all(row['status']=='PENDING' for row in state['stage_states'][3:])


def test_small_startup_benchmark_is_not_extrapolated_to_full_disk():
    tracker = Progress(10**12,256)
    rows=rows_before_write()
    state=tracker.snapshot(rows,2,STAGES[1],4194304,1)
    assert state['overall_eta_seconds'] is None


def test_all_io_passed_still_waits_for_final_health_checks():
    tracker=Progress(64*1048576,256)
    rows=[{'name':name,'status':'PASS','bytes':tracker.expected[i],'seconds':1} for i,name in enumerate(STAGES)]
    assert tracker.snapshot(rows,10)['overall_eta_seconds'] is None
    assert tracker.snapshot(rows,11,final_status='WARNING')['overall_eta_seconds']==0
    assert tracker.snapshot(rows,11,final_status='FAIL')['overall_eta_seconds'] is None


@pytest.mark.parametrize('offsets,expected', [((16,8,0),'BGRA'),((0,8,16),'RGBA')])
def test_framebuffer_respects_driver_reported_channel_order(offsets,expected):
    var=Variable();fix=Fixed();var.bits_per_pixel=32;fix.visual=2
    for channel,offset in zip((var.red,var.green,var.blue),offsets):
        channel.length=8;channel.offset=offset
    assert pixel_mode(var,fix)==expected
    fix.visual=3
    with pytest.raises(ValueError):pixel_mode(var,fix)


def test_graphical_error_restores_terminal_without_interrupting_test(monkeypatch):
    from io import StringIO
    from disktest import dashboard, framebuffer, graphics
    from disktest.safety import Identity
    class Terminal(StringIO):
        def isatty(self):return True
    closed=[]
    class Device:
        def close(self):closed.append(True)
    class BrokenRenderer:
        def __init__(self,*a,**kw):pass
        def frame(self,row):raise OSError('display unavailable')
    monkeypatch.setattr(dashboard.sys,'platform','linux')
    monkeypatch.setenv('VEDT_FRAMEBUFFER','1')
    monkeypatch.setattr(framebuffer,'Framebuffer',Device)
    monkeypatch.setattr(graphics,'PanelRenderer',BrokenRenderer)
    stream=Terminal()
    screen=dashboard.Dashboard(Identity('SN','Model',64*1048576,'wwn'),stream)
    screen(Progress(64*1048576,256).snapshot([],0))
    assert closed and screen.display is None
    assert stream.getvalue().count('Bekliyor')==6


def test_final_panel_wait_is_interruptible_and_restores_display(monkeypatch):
    from types import SimpleNamespace
    from disktest import dashboard
    calls=[]
    screen=SimpleNamespace(display=SimpleNamespace(present=lambda frame:calls.append(frame)),
        renderer=SimpleNamespace(frame=lambda row:'final panel'),last={'final_status':'WARNING'},
        close=lambda:calls.append('closed'))
    monkeypatch.setattr(dashboard,'_latest',screen)
    def stop(_):raise KeyboardInterrupt
    monkeypatch.setattr(dashboard.time,'sleep',stop)
    dashboard.wait_for_result()
    assert calls==['final panel','closed']


def test_cancel_during_stage_start_never_launches_write_and_marks_stopped(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    from disktest import raw
    from disktest.safety import Identity
    calls=[]
    class Device:
        logical_sector=512
        path=Path('/owned-file-only')
        fd=123
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def boundary(self):pass
        def check_fd(self):pass
        def stats(self):return (0,0)
        def native_ids(self):return {}
    class Worker:
        returncode=0
        def __init__(self,command,**kwargs):self.command=command;calls.append(command)
        def communicate(self,**kwargs):return ('{}','')
    def result(*args,**kwargs):
        command=calls[-1]
        size=next(x.split('=')[1] for x in command if x.startswith('--size='))
        size=next((x.split('=')[1] for x in command if x.startswith('--io_size=')),size)
        return {'jobs':[{}]},int(size)
    monkeypatch.setattr(raw,'persistent_reports',lambda _:None)
    monkeypatch.setattr(raw.shutil,'which',lambda _:'fake-fio')
    monkeypatch.setattr(raw.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='fio-3.39'))
    monkeypatch.setattr(raw.subprocess,'Popen',Worker)
    monkeypatch.setattr(raw,'PinnedDevice',Device)
    monkeypatch.setattr(raw,'parse_result',result)
    monkeypatch.setattr(raw,'read_smart',lambda *a,**kw:{'health':'PASS','temperature_c':None,'raw':{}})
    stopped=[]
    def event(row):
        if row.get('stage_index')==2 and row.get('event_kind')=='begin' and not stopped:
            stopped.append(True)
            raise KeyboardInterrupt
    target=Identity('SN','Model',64*1048576,'wwn')
    report=raw.run_raw(raw.RawSettings(target,allow_destroy=True),target.serial,tmp_path,event,accept_data_loss=True)
    assert report['status']=='CANCELLED'
    assert report['stages'][-1]['status']=='STOPPED'
    assert len(calls)==2 and all('--readonly' in command for command in calls)
    assert not report['full_capacity_verified']
