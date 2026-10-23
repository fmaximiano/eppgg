import hashlib
from collections import Counter
from decimal import Decimal as D
from pathlib import Path

import pytest
from app.calculator import calculate, CalculationError
from app.database import CareerDataSet, initialize, store_career_data
from app.schemas import CareerData, Scenario

ROOT=Path(__file__).parents[1]


@pytest.fixture
def real_data():
    return CareerData.model_validate_json((ROOT/'data/career-2026.json').read_text())


def test_complete_source_checked_matrix(real_data):
    positions={(p.level,p.grade):p for p in real_data.positions}
    assert len(positions)==50
    assert positions['I','A'].salary==D('3773.24')
    assert positions['I','B'].salary==D('4404.05')
    assert positions['III','F'].salary==D('8285.44')
    assert positions['V','J'].salary==D('13538.20')
    assert positions['I','A'].points==D('600')
    assert positions['I','B'].points==D('830')
    assert positions['V','J'].points==D('2870')
    assert real_data.gdpi_point_share==D('.5')
    assert real_data.gdpi_reference_salary==positions['V','J'].salary


def test_each_source_is_preserved_exactly(real_data):
    assert len(real_data.evidence)==9
    for evidence in real_data.evidence:
        assert evidence['url'].startswith(('https://www.mg.gov.br/','https://www.almg.gov.br/'))
        assert hashlib.sha256((ROOT/evidence['path']).read_bytes()).hexdigest()==evidence['sha256']


def test_all_cargo_function_families_and_published_values(real_data):
    rows=real_data.commissions+real_data.functions
    assert Counter(r.kind for r in rows)=={'DAD':12,'DAI':40,'FGD':15,'FGI':14,'GTED':8,'GTEI':8}
    amounts={r.code:r.amount for r in rows}
    assert amounts['DAD-1']==D('800.99')
    assert amounts['DAD-6']==D('4004.97')
    assert amounts['DAD-12']==D('10922.63')
    assert amounts['DAI-40']==D('10922.63')
    assert amounts['DAI-31']==D('6808.45') # preservar diferença de centavo do PDF, sem presumir equivalência DAD-8
    assert amounts['FGD-15']==D('3197.81')
    assert amounts['FGI-14']==D('3197.81')
    assert amounts['GTED-8']==amounts['GTEI-8']==D('4000')


def test_gdpi_uses_half_of_annex_points_without_double_counting(real_data):
    # 600 × .5 × .0007 × 13538.20 × .93 = 2644.01046.
    r=calculate(Scenario(mode='real'),real_data)
    assert r['gdpi']['effective_points']==D('300')
    assert r['gdpi']['actual']==D('2644.01')
    assert r['gdpi']['ceiling']==D('2843.02')
    assert r['monthly']['gross']==D('6417.25')
    assert r['monthly']['net'] is None
    assert r['monthly']['deductions'] is None
    assert 'pension' not in r['monthly']
    assert r['annual']['net'] is None
    assert r['annual']['thirteenth']['gross']==D('6417.25')
    assert r['annual']['vacation']['gross']==D('8556.34')
    assert r['annual']['gross']==D('85563.34')


def test_every_real_position_and_gdpi_threshold(real_data):
    for p in real_data.positions:
        for adi in ('0','69.99','70','100'):
            r=calculate(Scenario(mode='real',level=p.level,grade=p.grade,adi=adi,ai='100'),real_data)
            assert r['monthly']['gross']>=p.salary
            if D(adi)<70:assert r['gdpi']['actual']==0
            else:assert r['gdpi']['actual']>0
            assert r['monthly']['net'] is None


def test_real_commission_and_functions_not_subject_to_same_percentage(real_data):
    s=Scenario(mode='real',commission='DAD-6',remuneration_option='b')
    r=calculate(s,real_data)
    assert r['monthly']['gross']==D('8419.74')
    r=calculate(s.model_copy(update={'function':'GTED-4'}),real_data)
    assert r['monthly']['gross']==D('9419.74') # GTE integral de 1000, não 500
    r=calculate(Scenario(mode='real',function='FGD-5'),real_data)
    assert r['monthly']['gross']==D('7218.24') # função integral de 800,99
    for updates in ({'remuneration_option':'a'},{'function':'GTEI-1'},{'function':'FGD-1'}):
        with pytest.raises(CalculationError):calculate(s.model_copy(update=updates),real_data)
    with pytest.raises(CalculationError):calculate(Scenario(mode='real',function='GTED-1'),real_data)


def test_real_data_loaded_idempotently_and_not_promoted_to_payroll(client,real_data):
    result=client.post('/api/calculate',json={'mode':'real'})
    assert result.status_code==200
    assert result.json()['monthly']['gross']=='6417.25'
    assert result.json()['monthly']['net'] is None
    assert client.post('/api/calculate',json={'mode':'official'}).status_code==422
    assert client.post('/api/calculate',json={'mode':'real','competence':'2025-12'}).status_code==422
    with client.app.state.sessions() as session:
        store_career_data(session,real_data)
        row=session.get(CareerDataSet,real_data.version)
        assert row.payload['positions'][0]['salary']=='3773.24'
        changed=real_data.model_copy(deep=True)
        changed.positions[0].salary=D('1')
        with pytest.raises(ValueError,match='conteúdo diferente'):store_career_data(session,changed)


def test_real_comparison_does_not_rank_unknown_net(client):
    r=client.post('/api/commission-options',json={'mode':'real','commission':'DAD-6','remuneration_option':'b','function':'GTED-1'})
    assert r.status_code==200
    r=r.json()
    assert len(r['results'])==2
    assert r['best_monthly'] is None and r['best_annual'] is None
    assert r['best_gross']==1
    assert r['results'][0]['scenario']['function'] is None
    assert r['results'][1]['difference']['gross']=='2252.49'
    assert all(x['difference']['monthly'] is None for x in r['results'])


def test_real_exports_keep_inputs_reusable_and_do_not_export_fake_deductions(client):
    payload={'mode':'real','function':'FGI-14'}
    r=client.post('/api/export/json',json=payload)
    assert r.status_code==200
    assert client.post('/api/calculate',json=r.json()['scenario']).json()==r.json()
    csv=client.post('/api/export/csv',json=payload)
    assert csv.status_code==200
    assert '6417.25' not in csv.text
    assert '9615.06' in csv.text
    assert 'não apurados' in csv.text


def test_real_catalog_career_and_retroactive(client):
    r=client.get('/api/career-data')
    assert r.status_code==200
    assert len(r.json()['positions'])==50
    assert r.json()['status']=='real'
    assert client.get('/api/career-data?competence=invalid').status_code==422
    r=client.post('/api/career',json={'scenario':{'mode':'real'},'future_level':'I','future_grade':'B','years':5})
    assert r.status_code==200
    r=r.json()
    assert r['monthly_difference'] is None
    assert D(r['gross_monthly_difference'])>0
    assert r['series'][-1]['accumulated_difference'] is None
    assert D(r['series'][-1]['accumulated_gross_difference'])==5*D(r['gross_annual_difference'])
    r=client.post('/api/retroactive',json={'entries':[[{'mode':'real'},{'mode':'real','grade':'B'}]]})
    assert r.status_code==200
    assert r.json()['total_net_difference'] is None
    assert D(r.json()['total_gross_difference'])>0


def test_incomplete_matrix_and_wrong_reference_are_rejected(real_data):
    data=real_data.model_dump(mode='json')
    data['positions'][1]=data['positions'][0]
    with pytest.raises(ValueError,match='50 posições'):CareerData.model_validate(data)
    data=real_data.model_dump(mode='json')
    data['gdpi_reference_salary']='5047.65'
    with pytest.raises(ValueError,match='VBref'):CareerData.model_validate(data)
