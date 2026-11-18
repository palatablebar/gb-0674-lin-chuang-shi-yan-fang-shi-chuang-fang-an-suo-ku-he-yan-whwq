from copy import deepcopy
from fastapi.testclient import TestClient
from app import main
from app.archive import serialize
from app.coerce import instant
from app.cycles import episodes, current, attribute, CURRENT, PRIOR
from app.engine import evaluate
from app.errors import BusinessError
from app.modules.archive.rules import freeze
from app.modules.protocol.rules import normalize
import io, json, zipfile, pytest

@pytest.fixture
def reentry():
    return evaluate({'dataset':'reentry'})

def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DB_PATH',str(tmp_path/'test.sqlite'));return TestClient(main.app)

# 当前周期裁决：最晚入组为当前周期，全部模块共用
def test_current_cycle_is_latest_enrollment(reentry):
    ctx=reentry['context']
    assert [e['cycle'] for e in episodes('00021',ctx)]==[1,2]
    assert current('00021',ctx)['enrolled']=='2026-10-01T00:00:00+08:00'
    assert attribute('00021',instant('2026-09-01T00:00:00+08:00'),ctx)['cycle_role']==PRIOR

def test_single_cycle_default(reentry):
    assert current('00022',reentry['context'])['cycle']==1

# 同一重新入组重试不新增当前周期访视
def test_reenrollment_retry_deduped(reentry):
    ctx=deepcopy(reentry['context']);ctx['cycles']['00021'].append(dict(ctx['cycles']['00021'][1]))
    assert len(episodes('00021',ctx))==2

def test_same_reenrollment_retry_adds_no_visits(reentry):
    ctx=deepcopy(reentry['context'])
    retry=evaluate({'dataset':'reentry','overrides':{'cycles':{'00021':ctx['cycles']['00021']+[dict(ctx['cycles']['00021'][1])]}}})
    assert retry['balance']['expected']==reentry['balance']['expected']==4
    assert retry['balance']['completed']==reentry['balance']['completed']==3

# 记录归属：旧周期保留为证据，不进入当前周期计算
def test_records_split_by_cycle(reentry):
    assert {r['id'] for r in reentry['prior_records']}=={'00021-O-V1','00021-O-V2'}
    assert all(r['cycle']==1 and r['cycle_role']==PRIOR and r['cycle_status']=='筛选失败' for r in reentry['prior_records'])
    current_ids={r['id'] for r in reentry['records']}
    assert '00021-N-V1' in current_ids and not {'00021-O-V1','00021-O-V2'} & current_ids
    assert all(r['cycle_role']==CURRENT for r in reentry['records'])

def test_enrollment_outside_cycles_conflicts(reentry):
    with pytest.raises(BusinessError) as e:
        normalize(dict(reentry['records'][0],enrolled='2026-08-01T00:00:00+08:00'),reentry['context'])
    assert e.value.code=='ENROLLMENT_CONFLICT'

# 旧周期记录不能顶替新周期访视；连续计算会提前放行的陷阱被阻断
def test_prior_visits_do_not_complete_current_cycle(reentry):
    assert any(d['subject']=='00021' and d['visit']=='V2' and d['code']=='MISSING_PRIMARY' for d in reentry['deviations'])
    assert reentry['balance']['completed']==3 and reentry['balance']['expected']==4
    assert reentry['balance']['status']=='待处理'

def test_no_duplicate_primary_across_cycles(reentry):
    assert not any(d['code']=='DUPLICATE_PRIMARY' for d in reentry['deviations'])

def test_deviation_note_flags_prior_evidence(reentry):
    issue=next(d for d in reentry['deviations'] if d['subject']=='00021')
    assert issue['note']=='存在旧周期记录，不能顶替当前周期访视'

def test_cross_cycle_retest_blocked(reentry):
    issue=next(i for i in reentry['retest_issues'] if i['id']=='00021-N-R1')
    assert issue['code']=='RETEST_REFERENCE' and issue['parent']=='00021-O-V1'

def test_prior_windows_use_own_baseline(reentry):
    w=next(w for w in reentry['prior_windows'] if w['id']=='00021-O-V1')
    assert w['day']==7 and w['code']=='IN_WINDOW' and w['cycle_role']==PRIOR
    assert len(reentry['windows'])==4

# 行守恒：切分后旧周期记录仍计入对账
def test_row_conservation_includes_prior(reentry):
    b=reentry['balance']
    assert b['input']==6 and b['accepted']==6 and b['prior']==2 and b['row_balanced']

# 归档不丢失记录：封存与导出都覆盖旧周期证据
def test_archive_seal_covers_prior(reentry):
    s=deepcopy(reentry);s['prior_windows'][0]['day']=99
    assert freeze(s)['seal']!=reentry['archive']['seal']
    assert reentry['archive']['prior']==2

def test_export_preserves_prior_records(reentry):
    z=zipfile.ZipFile(io.BytesIO(serialize(reentry)))
    d=json.loads(z.read('evidence.json'))
    assert {r['id'] for r in d['prior_records']}=={'00021-O-V1','00021-O-V2'}

# 重算失败保留旧版锁库结论
def test_failed_rerun_keeps_lock_conclusion(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={'dataset':'reentry'}).json();rid=run['manifest']['run_id']
    def broken(*args,**kwargs): raise BusinessError('RECALC_FAILED','重算失败')
    monkeypatch.setattr(main,'evaluate',broken)
    assert c.post(f'/api/runs/{rid}/rerun').status_code==422
    kept=c.get(f'/api/runs/{rid}').json()
    assert kept['balance']['status']==run['balance']['status']=='待处理'
    assert kept['manifest']['sha256']==run['manifest']['sha256']

# 同一重新入组批次幂等
def test_reentry_dataset_idempotent(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    a=c.post('/api/runs',json={'dataset':'reentry'}).json();b=c.post('/api/runs',json={'dataset':'reentry'}).json()
    assert a['manifest']['run_id']==b['manifest']['run_id'];assert len(c.get('/api/runs').json())==1

def test_reentry_pages_render(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    run=c.post('/api/runs',json={'dataset':'reentry'}).json();rid=run['manifest']['run_id']
    for key in main.MODULES:
        response=c.get('/'+key+'?run_id='+rid)
        assert response.status_code==200 and '旧周期' in response.text
