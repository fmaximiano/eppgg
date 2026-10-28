from decimal import Decimal as D
import pytest
from pydantic import ValidationError
from app.calculator import calculate, progressive, income_tax, health, CalculationError, money
from app.schemas import Scenario, Beneficiary, Rubric


def test_monthly_independent_expected_values(parameters, scenario):
    result = calculate(scenario, parameters)
    m = result['monthly']
    # VB 4000; GDPI 600 * .0007 * 10000 * .93 = 3906.
    assert m['gross'] == D('7906.00')
    assert m['pension']['amount'] == D('1035.90')
    assert m['income_tax']['method'] == 'legal'
    assert m['income_tax']['base'] == D('6870.10')
    assert m['income_tax']['amount'] == D('980.55')
    assert m['net'] == D('5889.55')
    assert result['gdpi']['evaluation'] == D('.93')


@pytest.mark.parametrize('adi,expected',[('69.99','0'),('70','2940'),('100','4200')])
def test_gdpi_minimum(parameters, adi, expected):
    # AI=ADI is used to isolate the individual threshold.
    s=Scenario(adi=adi, ai=adi)
    r=calculate(s, parameters)
    assert r['gdpi']['actual'] == D(expected)


def test_gdpi_modes_and_ineligibility(parameters):
    assert calculate(Scenario(gdpi_evaluation='no_institutional'),parameters)['gdpi']['actual'] == D('3990')
    assert calculate(Scenario(gdpi_evaluation='statutory_70',adi='0'),parameters)['gdpi']['actual'] == D('2940')
    assert calculate(Scenario(gdpi_eligible=False),parameters)['gdpi']['actual'] == 0


def test_all_positions_and_evaluation_range(parameters):
    for pos in parameters.positions:
        for adi in ('0','69.99','70','95','100'):
            r=calculate(Scenario(level=pos.level,grade=pos.grade,adi=adi),parameters)
            assert r['monthly']['gross'] >= pos.salary
            assert r['gdpi']['actual'] <= r['gdpi']['ceiling']


def test_no_inferred_position(parameters):
    with pytest.raises(CalculationError, match='não cadastrado'):
        calculate(Scenario(level='VI'),parameters)


@pytest.mark.parametrize('base,expected', [('0','0'),('1500','165'),('1500.01','165'),('3000','345'),('4500','540'),('6000','750'),('10000','1350'),('20000','2900'),('21000','3060')])
def test_pension_progressive_boundaries(parameters, base, expected):
    assert progressive(D(base),parameters.pension_bands)[0] == D(expected)


def test_commission_choices_and_independent_pension(parameters):
    base=Scenario(commission='COMISSÃO DEMO',remuneration_option='a')
    a=calculate(base,parameters)
    assert a['monthly']['gross']==D('4000')
    assert a['monthly']['pension']['amount']==0
    b=calculate(base.model_copy(update={'remuneration_option':'b'}),parameters)
    assert b['monthly']['gross']==D('9906')
    assert b['monthly']['pension']['amount']==D('1035.90')
    opted=calculate(base.model_copy(update={'remuneration_option':'b','commission_pension':True}),parameters)
    assert opted['monthly']['pension']['base']==D('9906')
    parameters.commissions[0].allow_a=False
    with pytest.raises(CalculationError,match='não permitida'):
        calculate(base,parameters)


def test_capped_regime_and_complementary(parameters):
    s=Scenario(level='V',grade='J',capped_pension=True,complementary_rate='.085',complementary_deductible=True)
    m=calculate(s,parameters)['monthly']
    assert m['pension']['base']==D('8000')
    assert m['complementary']==money((m['bases']['pension']-D('8000'))*D('.085'))


def test_commission_preserves_effective_contribution_reference_when_configured(parameters):
    parameters.commissions[0].pension_basis_a='effective'
    s=Scenario(commission='COMISSÃO DEMO',remuneration_option='a')
    m=calculate(s,parameters)['monthly']
    assert m['gross']==D('4000')
    assert m['pension']['effective_reference_addition']==D('7906')
    assert m['pension']['base']==D('7906')
    assert m['pension']['amount']==D('1035.90')
    parameters.commissions[0].mandatory_pension=True
    m=calculate(s,parameters)['monthly']
    assert m['pension']['base']==D('11906')


@pytest.mark.parametrize('income', ['0','2428.80','2826.65','3751.05','4664.68','5000'])
def test_2026_full_reduction(parameters,income):
    assert income_tax(D(income),D('0'),0,parameters)['amount']==0


def test_reduction_uses_income_not_deduction_base(parameters):
    r=income_tax(D('7350.01'),D('3000'),0,parameters)
    assert r['base'] == D('4350.01')
    assert r['reduction'] == 0
    assert income_tax(D('6000'),D('0'),0,parameters)['reduction']==D('179.75')
    assert income_tax(D('7350'),D('0'),0,parameters)['reduction']==0
    assert income_tax(D('5000.01'),D('0'),0,parameters)['amount']>=0


@pytest.mark.parametrize('base,rate', [('2428.80','0'),('2428.81','.075'),('2826.65','.075'),('2826.66','.15'),('3751.05','.15'),('3751.06','.225'),('4664.68','.225'),('4664.69','.275')])
def test_tax_bracket_boundaries_without_reduction(parameters,base,rate):
    parameters.reduction_enabled=False
    parameters.tax_simplified=D('0')
    assert income_tax(D(base),D('0'),0,parameters)['rate']==D(rate)


def test_health_family_and_caps(parameters):
    s=Scenario(health_enrolled=True,age=60,beneficiaries=[Beneficiary(relationship='child',age=10) for _ in range(5)]+[Beneficiary(relationship='spouse',age=35),Beneficiary(relationship='child',age=21)])
    amount,rows=health(D('10000'),s,parameters)
    assert rows[0]['titular']==D('420')
    assert rows[0]['amount']==D('500')
    assert amount==D('910') # 500 + 320 + 90
    assert health(D('30000'),Scenario(health_enrolled=True,age=60),parameters)[0]==D('500')


def test_health_ages_minimum_and_unresolved_cases(parameters):
    parameters.health.low_income_rule='standard'
    assert health(D('1000'),Scenario(health_enrolled=True),parameters)[0]==D('60')
    for age,expected in [(20,'60'),(21,'90'),(38,'90')]:
        s=Scenario(health_enrolled=True,beneficiaries=[Beneficiary(relationship='child',age=age)])
        assert health(D('5000'),s,parameters)[0]==D('160')+D(expected)
    with pytest.raises(CalculationError,match='38'):
        health(D('5000'),Scenario(health_enrolled=True,beneficiaries=[Beneficiary(relationship='child',age=39)]),parameters)
    with pytest.raises(CalculationError,match='específica'):
        health(D('5000'),Scenario(health_enrolled=True,special_health=True),parameters)
    parameters.health.low_income_rule='unresolved'
    with pytest.raises(CalculationError,match='salários mínimos'):
        health(D('2000'),Scenario(health_enrolled=True),parameters)


def test_health_does_not_deduct_ir(parameters,scenario):
    without=calculate(scenario,parameters)['monthly']
    with_health=calculate(scenario.model_copy(update={'health_enrolled':True}),parameters)['monthly']
    assert without['income_tax']==with_health['income_tax']
    assert with_health['net']==without['net']-with_health['health']['amount']


def test_custom_earnings_incidence_and_partial_month(parameters):
    s=Scenario(fraction='.5',rubrics=[Rubric(name='Alimentação',amount='1000',source='Teste',proportional=True),Rubric(name='Consignado',amount='100',nature='deduction',source='Teste',proportional=True)])
    m=calculate(s,parameters)['monthly']
    assert m['gross']==D('4453')
    assert m['bases']['tax']==D('3953')
    assert m['other_deductions']==D('50')


def test_vacation_thirteenth_annual_separation(parameters,scenario):
    r=calculate(scenario,parameters)
    m,a=r['monthly'],r['annual']
    assert a['thirteenth']['net']==m['net']
    assert a['vacation']['gross']==D('10541.33')
    assert a['vacation']['pension']['amount']==m['pension']['amount']
    assert a['net']==11*m['net']+a['vacation']['net']+a['thirteenth']['net']
    parameters.health.thirteenth_incidence=None
    with pytest.raises(CalculationError,match='13º'):
        calculate(Scenario(health_enrolled=True),parameters)
    assert calculate(Scenario(health_enrolled=True,project_annual=False),parameters)['annual'] is None


def test_deductions_and_tax_dependents(parameters):
    r=calculate(Scenario(tax_dependents=2,alimony='500',alimony_deductible=True),parameters)['monthly']
    assert r['income_tax']['legal_deductions']==D('1915.08')
    assert r['alimony']==D('500')


@pytest.mark.parametrize('kwargs',[{'adi':'NaN'},{'adi':'Infinity'},{'fraction':'-1'},{'tax_dependents':-1},{'remuneration_option':'a'},{'commission_pension':True},{'complementary_rate':'.085'},{'beneficiaries':[{'relationship':'child','age':10}]}])
def test_invalid_inputs_rejected(kwargs):
    with pytest.raises(ValidationError): Scenario(**kwargs)


def test_missing_historical_or_official_data_blocks(parameters):
    for s in (Scenario(mode='official'),Scenario(competence='2016-10')):
        with pytest.raises(CalculationError):calculate(s,parameters)


def test_copay_is_charged_once_in_annual_projection(parameters):
    baseline = calculate(Scenario(health_enrolled=True), parameters)
    charged = calculate(Scenario(health_enrolled=True, copay='123.45'), parameters)
    assert baseline['monthly']['net'] - charged['monthly']['net'] == D('123.45')
    assert baseline['annual']['net'] - charged['annual']['net'] == D('123.45')
    for kind in ['vacation', 'thirteenth']:
        assert charged['annual'][kind]['health']['copay'] == 0
        assert charged['annual'][kind]['net'] == baseline['annual'][kind]['net']
    assert charged['annual']['vacation_increment_net'] == baseline['annual']['vacation_increment_net']
