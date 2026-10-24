"""Pagamento RRA, múltiplas fontes e migração imutável dos parâmetros."""
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

import pytest
from app.database import ParameterSet, initialize, resolve_parameters, store_parameters
from app.schemas import Parameters

ROOT=Path(__file__).parents[1]


def test_a_keeps_eligible_gdpi_replaces_salary_and_has_no_double_pension(client):
    base={'mode':'real','commission':'DAD-6','remuneration_option':'a'}
    m=client.post('/api/calculate',json=base).json()['monthly']
    assert m['gross']=='6648.98' # DAD4004.97 + GDPI2644.01, sem VB3773.24.
    assert [r['name'] for r in m['earnings']]==['GDPI','DAD-6 integral']
    assert m['pension']['base']=='6417.25' # referência VB3773.24 + GDPI2644.01.
    assert m['pension']['amount']=='795.88'
    opted=client.post('/api/calculate',json={**base,'commission_pension':True}).json()['monthly']
    assert opted['pension']['base']=='6648.98' # não VB + DAD + GDPI.
    assert opted['pension']['amount']=='830.64'
    assert D(opted['net'])<D(m['net'])
    poor=client.post('/api/calculate',json={**base,'commission':'DAI-1','commission_pension':True}).json()['monthly']
    assert poor['pension']['base']=='6417.25' # comissão inferior ao VB não reduz a referência.
    no_gdpi=client.post('/api/calculate',json={**base,'gdpi_eligible':False}).json()
    assert no_gdpi['monthly']['gross']=='4004.97'
    assert no_gdpi['monthly']['pension']['base']=='3773.24'
    assert no_gdpi['gdpi']['actual']=='0'
    assert client.post('/api/calculate',json={**base,'function':'GTED-4'}).json()['monthly']['gross']=='7648.98'


def test_a_is_available_for_each_real_commission_and_reusable_exports(client):
    p=client.get('/api/parameters?mode=real').json()
    assert p['version']=='eppgg-folha-real-2026-v4'
    for commission in p['commissions']:
        assert commission['allow_a'] and commission['a_keep_gdpi']
        response=client.post('/api/calculate',json={'mode':'real','commission':commission['code'],'remuneration_option':'a'})
        assert response.status_code==200
        assert D(response.json()['monthly']['gross'])==D(commission['amount'])+D('2644.01')
    payload={'mode':'real','commission':'DAD-6','remuneration_option':'a'}
    r=client.post('/api/export/json',json=payload)
    assert client.post('/api/calculate',json=r.json()['scenario']).json()==r.json()
    assert ';Líquido;' in client.post('/api/export/csv',json=payload).text


def rra(**updates):
    return {'payment_competence':'2026-10','last_origin_year':2025,'months':'12','taxable_income':'60000',**updates}


def test_rra_uses_scaled_table_without_monthly_reduction_or_simplified(client):
    # 60000*.275 - 908.73*12 = 5595.24, mesmo com renda equivalente5000.
    r=client.post('/api/rra',json=rra())
    assert r.status_code==200
    result=r.json()
    assert result['base']=='60000.00'
    assert result['income_tax']=='5595.24'
    assert result['net_after_legal_expenses']=='54404.76'
    assert result['parameters']['version']=='eppgg-folha-real-2026-v4'
    assert result['request']==rra(exempt_income='0',official_pension='0',alimony='0',legal_expenses='0',other_deductions='0',mode='real')
    assert client.post('/api/rra',json=result['request']).json()==result


def test_rra_deductions_exempt_portion_and_actual_payment(client):
    r=client.post('/api/rra',json=rra(exempt_income='1000',official_pension='6600',alimony='2400',legal_expenses='3000',other_deductions='100')).json()
    assert r['gross']=='61000.00'
    assert r['base']=='48000.00'
    assert r['income_tax']=='2694.12' #48000*.225 - 675.49*12.
    assert r['net_payment_before_legal_expenses']=='49205.88'
    assert r['net_after_legal_expenses']=='46205.88'


@pytest.mark.parametrize('months,income,expected',[('12','29145.60','0.00'),('1.5','7500','699.41'),('1','2500','5.34')])
def test_rra_fractional_months_brackets_and_no_ten_reais_waiver(client,months,income,expected):
    r=client.post('/api/rra',json=rra(months=months,taxable_income=income))
    assert r.status_code==200
    assert r.json()['income_tax']==expected


@pytest.mark.parametrize('updates',[{'last_origin_year':2026},{'months':'0'},{'months':'-1'}, {'official_pension':'60001'}, {'payment_competence':'2027-01'}, {'tax_dependents':1}, {'mode':'demo'}])
def test_rra_rejects_unsupported_or_incoherent_payment(client,updates):
    assert client.post('/api/rra',json=rra(**updates)).status_code==422


def employments(payer2='Estado de Minas Gerais',**updates):
    a={'name':'Vínculo 1','mode':'real','health_enrolled':True}
    b={'name':'Vínculo 2','mode':'real','health_enrolled':True}
    return {'lawful_accumulation_confirmed':True,'employments':[{'payer':'Estado de Minas Gerais','scenario':a},{'payer':payer2,'scenario':b}],**updates}


def test_multiple_same_payer_aggregate_ir_and_single_health(client):
    response=client.post('/api/multiple-employments',json=employments())
    assert response.status_code==200
    r=response.json();m=r['monthly']
    assert m['gross']=='12834.50'
    assert [e['pension']['amount'] for e in m['employments']]==['795.88','795.88']
    assert m['health']['amount']=='205.35'
    assert len(m['income_tax_sources'])==1
    assert m['income_tax_sources'][0]['income_tax']['amount']=='2183.02' # (12834.50-1591.76)*.275-908.73.
    assert m['net']=='8854.37'
    assert D(r['annual']['net'])==11*D(m['net'])+D(r['annual']['vacation']['net'])+D(r['annual']['thirteenth']['net'])
    assert client.post('/api/multiple-employments',json=r['request']).json()==r


def test_distinct_payers_and_normalized_payer_name(client):
    m=client.post('/api/multiple-employments',json=employments('Outra fonte')).json()['monthly']
    assert len(m['income_tax_sources'])==2
    assert [t['income_tax']['amount'] for t in m['income_tax_sources']]==['512.95','512.95']
    assert m['health']['amount']=='205.35' and m['net']=='10011.49'
    m=client.post('/api/multiple-employments',json=employments('  ESTADO  de Minas Gerais ')).json()['monthly']
    assert len(m['income_tax_sources'])==1


def test_health_uses_larger_state_income_and_applies_family_once(client):
    request=employments()
    request['employments'][1]['scenario']['grade']='B'
    for e in request['employments']:
        e['scenario'].update(beneficiaries=[{'relationship':'child','age':10}],copay='15',other_deductions='10',tax_dependents=1)
    r=client.post('/api/multiple-employments',json=request)
    assert r.status_code==200
    m=r.json()['monthly']
    assert m['health']['employment_index']==1
    assert m['health']['base']=='8061.60'
    assert m['health']['amount']=='321.21' #257.97 +63.24, uma vez.
    assert m['income_tax_sources'][0]['income_tax']['legal_deductions']==str(D('795.88')+D(m['employments'][1]['pension']['amount'])+D('189.59'))
    assert [e['copay'] for e in m['employments']]==['15','15']


def test_external_source_uses_reported_contribution_not_eppgg_pension(client):
    request=employments()
    request['employments'][1]={'payer':'Empresa','reported':{'name':'Emprego CLT','gross':'3000','taxable_income':'3000','official_pension':'248.60'}}
    r=client.post('/api/multiple-employments',json=request)
    assert r.status_code==200
    result=r.json();m=result['monthly']
    assert m['employments'][1]['pension']['amount']=='248.60'
    assert m['health']['base']=='6417.25'
    assert m['income_tax_sources'][1]['income_tax']['amount']=='0.00'
    assert m['net']=='7654.47' #4903.07+3000-248.60.
    assert result['annual'] is None #não inventar 13º/férias do contracheque.


@pytest.mark.parametrize('change', ['confirmation','family','period','mode','no_scenario','ambiguous','bad_external'])
def test_multiple_rejects_conflicting_inputs(client,change):
    request=employments()
    if change=='confirmation':request['lawful_accumulation_confirmed']=False
    if change=='family':request['employments'][1]['scenario']['age']=60
    if change=='period':request['employments'][1]['scenario']['competence']='2026-09'
    if change=='mode':request['employments'][1]['scenario']['mode']='demo'
    if change=='no_scenario':request['employments'][0]={'payer':'Empresa','reported':{'name':'CLT','gross':100,'taxable_income':100}}
    if change=='ambiguous':request['employments'][1]['reported']={'name':'CLT','gross':100,'taxable_income':100}
    if change=='bad_external':request['employments'][1]={'payer':'Empresa','reported':{'name':'CLT','gross':100,'taxable_income':200}}
    assert client.post('/api/multiple-employments',json=request).status_code==422


def test_successor_keeps_v1_bytes_and_history_immutable(client):
    v1=Parameters.model_validate_json((ROOT/'data/payroll-2026.json').read_text())
    v2=Parameters.model_validate_json((ROOT/'data/payroll-2026-v2.json').read_text())
    assert not v1.commissions[0].allow_a and v2.commissions[0].allow_a
    assert v2.supersedes==[v1.version]
    with client.app.state.sessions() as s:
        assert s.get(ParameterSet,v1.version).payload['commissions'][0]['allow_a'] is False
        assert resolve_parameters(s,'2026-10','official').version=='eppgg-folha-real-2026-v4'
        store_parameters(s,v1);store_parameters(s,v2)
        changed=v1.model_copy(update={'source':'changed'})
        with pytest.raises(ValueError,match='diferente'):store_parameters(s,changed)
        invalid=v2.model_copy(update={'version':'invalid','supersedes':['missing']})
        with pytest.raises(ValueError,match='existir'):store_parameters(s,invalid)
    for e in v2.evidence:
        assert hashlib.sha256((ROOT/e['path']).read_bytes()).hexdigest()==e['sha256']


def test_upgrade_from_existing_v1_preserves_payload_and_is_idempotent(tmp_path):
    from app.database import Base, create_db
    v1=Parameters.model_validate_json((ROOT/'data/payroll-2026.json').read_text())
    engine,sessions=create_db('sqlite:///'+str(tmp_path/'upgrade.db'))
    Base.metadata.create_all(engine)
    with sessions() as s:
        store_parameters(s,v1)
        original=dict(s.get(ParameterSet,v1.version).payload)
    initialize(engine,sessions);initialize(engine,sessions)
    with sessions() as s:
        assert s.get(ParameterSet,v1.version).payload==original
        assert resolve_parameters(s,'2026-10','real').version=='eppgg-folha-real-2026-v4'
    engine.dispose()


def test_successor_rejects_partial_coverage_and_unlisted_overlap(client):
    from datetime import date
    v2=Parameters.model_validate_json((ROOT/'data/payroll-2026-v2.json').read_text())
    with client.app.state.sessions() as s:
        partial=v2.model_copy(update={'version':'partial','valid_until':date(2026,10,31)})
        with pytest.raises(ValueError,match='cobertura integral'):store_parameters(s,partial)
        fork=v2.model_copy(update={'version':'fork'})
        with pytest.raises(ValueError,match='sobrepostas'):store_parameters(s,fork)


def test_external_state_health_and_same_payer_aggregate(client):
    request=employments()
    request['employments'][1]={'payer':'Estado de Minas Gerais','reported':{'name':'Outro cargo estadual','gross':'10000','taxable_income':'10000','official_pension':'1500','ipsemg_base':'10000','deductible_complementary':'200','alimony':'100','alimony_deductible':True}}
    r=client.post('/api/multiple-employments',json=request)
    assert r.status_code==200
    m=r.json()['monthly']
    assert m['health']['base']=='10000' and m['health']['amount']=='320.00'
    tax=m['income_tax_sources'][0]['income_tax']
    assert tax['legal_deductions']=='2595.88'
    assert tax['income']=='16417.25'
    assert tax['amount']=='2892.15' #13821.37*.275-908.73.


def test_custom_parameters_are_not_replaced_by_successor(tmp_path):
    from app.database import Base, create_db
    p=Parameters.model_validate_json((ROOT/'data/payroll-2026.json').read_text()).model_copy(update={'version':'custom-real'})
    engine,sessions=create_db('sqlite:///'+str(tmp_path/'custom.db'))
    Base.metadata.create_all(engine)
    with sessions() as s:store_parameters(s,p)
    initialize(engine,sessions)
    with sessions() as s:
        assert resolve_parameters(s,'2026-10','real').version=='custom-real'
        assert s.get(ParameterSet,'eppgg-folha-real-2026-v2') is None
    engine.dispose()


def test_numeric_limits_return_validation_errors_instead_of_decimal_overflow(client):
    for update in ({'months':'1e-999999'},{'official_pension':'1e999999'}):
        assert client.post('/api/rra',json=rra(**update)).status_code==422
    request=employments()
    request['employments'][1]={'payer':'Empresa','reported':{'name':'CLT','gross':'1000','taxable_income':'1000','official_pension':'1e999999'}}
    assert client.post('/api/multiple-employments',json=request).status_code==422
