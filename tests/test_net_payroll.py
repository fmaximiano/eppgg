"""Casos reais: valores independentes e fronteiras das regras de folha de 2026."""
import hashlib
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlalchemy import select
from app.calculator import calculate, health, income_tax, progressive, CalculationError
from app.database import Base, ParameterSet, create_db, initialize, resolve_parameters, store_parameters
from app.schemas import Parameters, Scenario

ROOT=Path(__file__).parents[1]

@pytest.fixture
def payroll():
    return Parameters.model_validate_json((ROOT/'data/payroll-2026.json').read_text())


def test_real_monthly_reference_and_health_does_not_deduct_ir(payroll):
    # RPPS = 2083.80*.11 + 1389.17*.12 + 1389.21*.13 + 1389.19*.14 + 165.88*.15.
    # IR = (6417.25-795.88)*.275 - 908.73 - round(978.62-.133145*6417.25,2).
    r=calculate(Scenario(mode='real'),payroll)
    m=r['monthly']
    assert (m['gross'],m['pension']['amount'],m['income_tax']['amount'],m['net'])==tuple(map(D,['6417.25','795.88','512.95','5108.42']))
    insured=calculate(Scenario(mode='real',health_enrolled=True),payroll)['monthly']
    assert insured['health']['amount']==D('205.35')
    assert insured['income_tax']==m['income_tax']
    assert insured['net']==D('4903.07')
    assert r['evidence'] and r['pension_revaluation'] and r['pending']


def test_payroll_evidence_and_revaluation_are_preserved(payroll):
    assert len(payroll.evidence)>=20
    for e in payroll.evidence:
        assert hashlib.sha256((ROOT/e['path']).read_bytes()).hexdigest()==e['sha256']
    assert [b.upper for b in payroll.pension_bands]==list(map(D,['2083.80','3472.97','4862.18','6251.37','7640.56','8475.55']))+[None]
    assert payroll.pension_revaluation[-1]['upper_limits'][-1]=='8475.55'
    assert payroll.health.minimum==D('63.24') and payroll.health.maximum==D('527')


@pytest.mark.parametrize('base,expected',[
    ('2083.80','229.22'),('3472.97','395.92'),('4862.18','576.52'),
    ('6251.37','771.00'),('7640.56','979.38'),('8475.55','1108.80'),('9475.55','1268.80')])
def test_progressive_band_reference_values(payroll,base,expected):
    amount,rows=progressive(D(base),payroll.pension_bands)
    assert amount==D(expected)
    assert sum(r['base'] for r in rows)==D(base)


def test_all_positions_have_net_and_capped_pension_respects_ceiling(payroll):
    for p in payroll.positions:
        r=calculate(Scenario(mode='real',level=p.level,grade=p.grade,health_enrolled=True),payroll)
        assert D('0')<r['monthly']['net']<r['monthly']['gross']
        assert r['annual']['net']==11*r['monthly']['net']+r['annual']['vacation']['net']+r['annual']['thirteenth']['net']
    s=Scenario(mode='real',level='V',grade='J',capped_pension=True,complementary_rate='.085')
    m=calculate(s,payroll)['monthly']
    assert m['pension']['base']==D('8475.55')
    assert m['pension']['amount']==D('1108.80')
    assert m['complementary']>0


def test_commission_and_function_pension_are_explicit_options(payroll):
    for kwargs,flag in [({'commission':'DAD-6','remuneration_option':'b'},'commission_pension'),({'function':'FGD-5'},'function_pension')]:
        s=Scenario(mode='real',**kwargs)
        a=calculate(s,payroll)['monthly']
        b=calculate(s.model_copy(update={flag:True}),payroll)['monthly']
        assert a['gross']==b['gross']
        assert a['pension']['base']==D('6417.25')
        assert b['pension']['base']==b['gross']
        assert b['pension']['amount']>a['pension']['amount']
        assert b['net']<a['net']


@pytest.mark.parametrize('base,age,expected',[
    ('1000',59,'32.00'),('3242',59,'103.74'),('3242.01',58,'103.74'),
    ('3242.01',59,'136.16'),('10000',58,'320.00'),('10000',59,'420.00'),
    ('20000',59,'727.00'),('60000',59,'1054.00')])
def test_health_income_age_and_separate_additional_cap(payroll,base,age,expected):
    s=Scenario(mode='real',health_enrolled=True,age=age)
    assert health(D(base),s,payroll)[0]==D(expected)


@pytest.mark.parametrize('age,expected',[ (20,'383.24'),(21,'414.86'),(38,'414.86') ])
def test_children_age_boundaries(payroll,age,expected):
    s=Scenario(mode='real',health_enrolled=True,beneficiaries=[{'relationship':'child','age':age}])
    assert health(D('10000'),s,payroll)[0]==D(expected)


def test_children_low_income_cap_special_approval_and_parent_eligibility(payroll):
    s=Scenario(mode='real',health_enrolled=True,age=59,beneficiaries=[{'relationship':'child','age':20},{'relationship':'child','age':21}])
    assert health(D('2000'),s,payroll)[0]==D('128') # 64 titular + 0 menor + 64 adulto.
    assert health(D('3242'),s,payroll)[0]==D('198.60') # 103.74 + 0 + teto94.86.
    assert health(D('20000'),s,payroll)[0]==D('821.86') # teto527 + adicional200 + filho94.86.
    special={'relationship':'child','age':45,'special_condition':True}
    with pytest.raises(CalculationError,match='aprovada'):
        health(D('10000'),Scenario(mode='real',health_enrolled=True,beneficiaries=[special]),payroll)
    special['exemption_approved']=True
    assert health(D('10000'),Scenario(mode='real',health_enrolled=True,beneficiaries=[special]),payroll)[0]==D('320')
    parent={'relationship':'parent','age':65}
    with pytest.raises(CalculationError,match='dependência'):
        health(D('10000'),Scenario(mode='real',health_enrolled=True,beneficiaries=[parent]),payroll)
    parent['eligibility_confirmed']=True
    assert health(D('10000'),Scenario(mode='real',health_enrolled=True,beneficiaries=[parent]),payroll)[0]==D('740')
    with pytest.raises(CalculationError,match='acumulados'):
        health(D('10000'),s.model_copy(update={'beneficiaries':Scenario(health_enrolled=True,beneficiaries=[parent,{'relationship':'child','age':10}]).beneficiaries}),payroll)
    with pytest.raises(CalculationError,match='39 anos'):
        health(D('10000'),Scenario(mode='real',health_enrolled=True,beneficiaries=[{'relationship':'sibling','age':39,'eligibility_confirmed':True}]),payroll)


def test_vacation_thirteenth_and_nonrecurring_deductions(payroll):
    r=calculate(Scenario(mode='real',health_enrolled=True,copay='30',other_deductions='100'),payroll)
    m=r['monthly'];v=r['annual']['vacation'];t=r['annual']['thirteenth']
    assert v['gross']==D('8556.34')
    assert v['pension']['base']==t['pension']['base']==m['pension']['base']==D('6417.25')
    assert v['health']['amount']==D('273.80')
    assert t['health']['amount']==D('205.35')
    assert t['health']['copay']==0 and t['other_deductions']==0
    assert t['income_tax']['exclusive'] is True
    assert v['income_tax']['income']==D('8556.34')


@pytest.mark.parametrize('income,expected',[('5000','0.00'),('6000','394.54'),('7350','945.54'),('7350.01','945.54')])
def test_ir_reduction_limits_using_revenue_examples(payroll,income,expected):
    assert income_tax(D(income),D(0),0,payroll)['amount']==D(expected)


def test_withholding_waiver_does_not_apply_to_thirteenth(payroll):
    a=income_tax(D('5020'),D('607.20'),0,payroll)
    assert D('0')<a['calculated_amount']<=10
    assert a['waiver_applied'] and a['amount']==0
    b=income_tax(D('5020'),D('607.20'),0,payroll,exclusive=True)
    assert not b['waiver_applied'] and b['amount']==a['calculated_amount']


def test_initialization_preserves_existing_custom_payroll(tmp_path,payroll):
    engine,sessions=create_db('sqlite:///'+str(tmp_path/'seed.db'))
    Base.metadata.create_all(engine)
    custom=payroll.model_copy(update={'version':'custom-2026'})
    with sessions() as session:store_parameters(session,custom)
    initialize(engine,sessions);initialize(engine,sessions)
    with sessions() as session:
        assert resolve_parameters(session,'2026-10','real').version=='custom-2026'
        assert session.get(ParameterSet,payroll.version) is None
    engine.dispose()
