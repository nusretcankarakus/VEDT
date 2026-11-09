from copy import deepcopy
import json
from pathlib import Path
import pytest
import sys
from disktest.installation_policy import installation_decision
from disktest.health import comparison_rows
from disktest.connection import connection_info
from disktest.charts import points, pauses, render_chart
from disktest.archive import build_index
from disktest.report import write_report, verify_manifest


def evidence():
    size=80*1024**3
    return {'id':'a'*24,'account_name':'VEDT54','version':'0.8.0.dev0','mode':'raw-device',
        'identity_authorized':True,'status':'WARNING','error':None,'warnings':['Geliştirme sürümü'],'elapsed_seconds':20,
        'started_at':'2026-11-09T12:00:00Z','full_capacity_verified':True,
        'target':{'bytes':size,'identity':{'serial':'SN-54','model':'Test SSD','wwn':'wwn','size_bytes':size}},
        'stages':[{'name':str(i),'status':'PASS','bytes':size,'seconds':2,'mib_per_s':100} for i in range(6)],
        'smart_before':{'health':'PASS','acquisition_ok':True,'raw':{'ata_smart_attributes':{'table':[{'id':197,'raw':{'value':0}}]}}},
        'smart_after':{'health':'PASS','acquisition_ok':True,'raw':{'ata_smart_attributes':{'table':[{'id':197,'raw':{'value':0}}]}}}}


def test_clean_test_eligible_despite_generic_development_warning():
    assert installation_decision(evidence())['eligible']


@pytest.mark.parametrize('case',['smart-missing','smart-warning','pending','counter-increase','counter-reset','partial','cancelled','bytes','worker'])
def test_policy_blocks_unreliable_or_unhealthy_test(case):
    s=evidence()
    if case=='smart-missing':s.pop('smart_after')
    if case=='smart-warning':s['smart_after']['health']='WARNING'
    if case=='pending':
        for k in ('smart_before','smart_after'):s[k]['raw']['ata_smart_attributes']['table'][0]['raw']['value']=1
    if case in ('counter-increase','counter-reset'):s['smart_changes']={'ata_199':{'before':0 if case=='counter-increase' else 5,'after':1,'delta':1 if case=='counter-increase' else -4}}
    if case=='partial':s['full_capacity_verified']=False
    if case=='cancelled':s['status']='CANCELLED'
    if case=='bytes':s['stages'][5]['bytes']=1
    if case=='worker':s['worker_may_still_be_running']=123
    assert not installation_decision(s)['eligible']


def test_smart_missing_is_not_zero_and_crc_is_visible():
    s=evidence();s['smart_changes']={'ata_199':{'before':2,'after':4,'delta':2}}
    rows={r['key']:r for r in comparison_rows(s)}
    assert rows['media_errors']['delta'] is None
    assert rows['ata_199']['delta']==2
    assert rows['ata_197']['delta']==0


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux sysfs paths contain colons')
def test_link_info_reads_closest_controller_and_sata(tmp_path):
    root=tmp_path/'sys';device=root/'devices/pci0000:00/0000:00:02.0/nvme/nvme0';device.mkdir(parents=True)
    pci=device.parents[1]
    (pci/'current_link_speed').write_text('8.0 GT/s PCIe')
    (pci/'current_link_width').write_text('4')
    node=root/'class/block/nvme0n1';node.mkdir(parents=True);(node/'device').symlink_to(device,target_is_directory=True)
    data=connection_info('/dev/nvme0n1',{'raw':{'device':{'protocol':'NVMe'}}},root)
    assert data['pcie_current_width']=='4' and data['pcie_current_speed']=='8.0 GT/s PCIe'
    assert data['pcie_maximum_speed'] is None
    (pci/'current_link_speed').write_text('Unknown')
    (pci/'current_link_width').write_text('255')
    unknown=connection_info('/dev/nvme0n1',{'raw':{}},root)
    assert unknown['pcie_current_speed'] is None and unknown['pcie_current_width'] is None
    sata=connection_info('/dev/absent',{'raw':{'interface_speed':{'current':{'string':'3.0 Gb/s'},'max':{'string':'6.0 Gb/s'}}}},root)
    assert sata['sata_current']=='3.0 Gb/s' and sata['pcie_current_width'] is None


def test_chart_excludes_invalid_data_and_marks_only_dense_zero_runs(tmp_path):
    s={'telemetry':[{'elapsed_seconds':i,'mib_per_s':0,'stage':'write'} for i in range(7)]}
    s['telemetry']+=[{'elapsed_seconds':8,'mib_per_s':float('nan')},{'elapsed_seconds':9,'mib_per_s':-1}]
    assert len(points(s,'speed'))==7 and pauses(s)[0]['seconds']==6
    assert pauses({'telemetry':[{'elapsed_seconds':i,'mib_per_s':0,'stage':'write'} for i in (0,20)]})==[]
    render_chart(s,'temperature',tmp_path/'missing.png')
    from PIL import Image
    assert Image.open(tmp_path/'missing.png').size==(1400,560)


def test_report_graphs_manifest_and_usb_wide_index(tmp_path):
    s=evidence();s['target']['identity']['serial']='<script>alert(1)</script>'
    root=tmp_path/'reports';job=root/'jobs'/'one';job.mkdir(parents=True)
    folder=write_report(s,job,with_pdf=False)
    assert verify_manifest(folder)==[]
    assert (folder/'speed.png').is_file() and (folder/'temperature.png').is_file()
    html=next(folder.glob('*.html')).read_text(encoding='utf-8')
    assert 'SMART önce / sonra' in html and 'Windows kurulum kararı' in html
    assert 'Test kapsamı ve sınırları' in html
    assert build_index(root)==1
    index=(root/'index.html').read_text(encoding='utf-8')
    assert 'VEDT54' in index and '&lt;script&gt;' in index and '<script>alert' not in index
    assert 'jobs/one/' in index and 'addEventListener' in index
    (folder/'speed.png').write_bytes(b'changed')
    assert verify_manifest(folder)


def test_resume_windows_gate_rechecks_current_smart_policy(tmp_path):
    from disktest.deployment import validate_installation_targets
    from disktest.report import digest
    s=evidence();s['smart_after']['health']='UNKNOWN'
    folder=write_report(s,tmp_path,with_pdf=False)
    plan={'targets':[{'test_report':s['id'],'identity':s['target']['identity'],'manifest_sha256':digest(folder/'manifest.json')}]}
    (tmp_path/'windows-hazirlik.json').write_text(json.dumps(plan),encoding='utf-8')
    with pytest.raises(ValueError,match='Windows kurulmayacak'):validate_installation_targets(tmp_path)
