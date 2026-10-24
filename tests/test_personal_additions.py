"""Adicionais reconhecidos: incidências, bases e preservação dos cenários antigos."""
import hashlib
from decimal import Decimal as D
from pathlib import Path

import pytest
from app.calculator import CalculationError, calculate
from app.database import ParameterSet, initialize, resolve_parameters
from app.schemas import Parameters, Scenario

ROOT = Path(__file__).parents[1]


@pytest.fixture
def payroll():
    return Parameters.model_validate_json((ROOT / 'data/payroll-2026-v5.json').read_text())


@pytest.fixture
def payroll_v4():
    return Parameters.model_validate_json((ROOT / 'data/payroll-2026-v4.json').read_text())


def additions(result):
    return {r['name']: r for r in result['monthly']['earnings'] if r['name'] in ('Quinquênio', 'ADE')}


def test_recognized_quinquennia_and_ade_net_reference(payroll):
    r = calculate(Scenario(mode='real', personal_additions_regime='ade_option', quinquennia=2, ade_percent=10, health_enrolled=True), payroll)
    rows = additions(r)
    # 3773.24*20% =754.65 e 3773.24*10%=377.32, sem cascata.
    assert rows['Quinquênio']['amount'] == D('754.65')
    assert rows['ADE']['amount'] == D('377.32')
    m = r['monthly']
    # RPPS:771.0023+(7549.22-6251.37)*15%=965.68.
    # IR:(7549.22-965.68)*27.5%-908.73=901.74; sem redução acima de7350.
    assert (m['gross'], m['pension']['amount'], m['health']['amount'], m['income_tax']['amount'], m['net']) == tuple(map(D, ['7549.22', '965.68', '241.58', '901.74', '5440.22']))
    assert r['annual']['thirteenth']['gross'] == D('7549.22')
    assert r['annual']['vacation']['gross'] == D('10065.63')
    assert r['annual']['vacation']['pension']['amount'] == m['pension']['amount']
    assert r['annual']['gross'] == D('100656.27')


def test_ade_is_granted_percentage_not_gdpi_score(payroll):
    s = Scenario(mode='real', personal_additions_regime='ade', ade_percent='5.4')
    a = additions(calculate(s, payroll))['ADE']
    b = additions(calculate(s.model_copy(update={'adi': D('70'), 'ai': D('0')}), payroll))['ADE']
    assert a == b
    assert a['amount'] == D('203.75')
    assert a['calculation']['method'] == 'granted_percentage'


def test_month_fraction_is_applied_once_to_integral_bases(payroll):
    r = calculate(Scenario(mode='real', personal_additions_regime='ade_option', quinquennia=2, ade_percent=6, fraction='.5', quinquennium_base='5000', ade_base='6000'), payroll)
    rows = additions(r)
    assert rows['Quinquênio']['amount'] == D('500.00')
    assert rows['ADE']['amount'] == D('180.00')
    assert rows['ADE']['calculation']['base'] == D('6000')


def test_old_versions_and_old_scenarios_have_no_automatic_additions(payroll):
    old = Parameters.model_validate_json((ROOT / 'data/payroll-2026-v2.json').read_text())
    s = Scenario(mode='real')
    before, after = calculate(s, old), calculate(s, payroll)
    assert before['monthly'] == after['monthly']
    assert before['annual'] == after['annual']
    assert not additions(after)
    with pytest.raises(CalculationError, match='Não há regras'):
        calculate(Scenario(mode='real', personal_additions_regime='ade', ade_percent=6), old)


@pytest.mark.parametrize('change', [
    {'quinquennia': 1}, {'ade_percent': 6},
    {'personal_additions_regime': 'ade', 'quinquennia': 1},
    {'personal_additions_regime': 'quinquennium', 'ade_percent': 6},
    {'personal_additions_regime': 'ade', 'ade_percent': '70.01'},
    {'personal_additions_regime': 'ade', 'ade_percent': '-1'},
    {'personal_additions_regime': 'quinquennium', 'quinquennia': '1.5'},
    {'personal_additions_regime': 'quinquennium', 'quinquennia': -1},
    {'personal_additions_regime': 'ade', 'ade_base': 100},
    {'personal_additions_regime': 'ade', 'ade_percent': 6, 'ade_base': 0},
])
def test_invalid_or_incompatible_rights_rejected(client, change):
    assert client.post('/api/calculate', json={'mode': 'real', **change}).status_code == 422


def test_career_comparison_exports_and_reference_bases(client):
    s = {'mode': 'real', 'personal_additions_regime': 'ade_option', 'quinquennia': 2, 'ade_percent': '10'}
    result = client.post('/api/career', json={'scenario': s, 'future_level': 'I', 'future_grade': 'B', 'years': 5})
    assert result.status_code == 200
    r = result.json()
    rows = additions(r['future'])
    assert rows['Quinquênio']['amount'] == '880.81'
    assert rows['ADE']['amount'] == '440.41'
    assert 'Não prevê novas aquisições' in r['assumptions']
    fixed = client.post('/api/career', json={'scenario': {**s, 'quinquennium_base': '5000', 'ade_base': '6000'}, 'future_level': 'I', 'future_grade': 'B', 'years': 5}).json()
    assert additions(fixed['current']) == additions(fixed['future'])
    compared = client.post('/api/compare', json={'scenarios': [{'mode': 'real'}, s]}).json()
    assert compared['results'][1]['monthly']['gross'] == '7549.22'
    memory = client.post('/api/export/json', json=s).json()
    assert additions(memory)['Quinquênio']['calculation']['quantity'] == 2
    assert client.post('/api/calculate', json=memory['scenario']).json()['monthly'] == memory['monthly']
    csv = client.post('/api/export/csv', json=s).text
    assert ';Quinquênio;754.65;Sim;Sim;Sim;' in csv
    assert 'Base integral: R$3773.24' in csv
    assert ';ADE;377.32;' in csv


def test_new_version_is_idempotent_and_keeps_prior_history(client, payroll):
    with client.app.state.sessions() as session:
        engine = session.get_bind()
    initialize(engine, client.app.state.sessions)
    with client.app.state.sessions() as session:
        assert resolve_parameters(session, '2026-10', 'real').version == payroll.version
        for name in ('payroll-2026.json', 'payroll-2026-v2.json'):
            old = Parameters.model_validate_json((ROOT / 'data' / name).read_text())
            assert session.get(ParameterSet, old.version).payload == old.model_dump(mode='json')
    for e in payroll.evidence:
        assert hashlib.sha256((ROOT / e['path']).read_bytes()).hexdigest() == e['sha256']
    catalog = client.get('/api/sources').json()['catalog']
    section = next(s for s in catalog['sections'] if s['id'] == 'personal-additions')
    assert len(section['items']) == 12


@pytest.mark.parametrize('count,percent', [(0,'0'),(2,'0'),(3,'6'),(4,'6'),(5,'10'),(9,'10'),(10,'20'),(14,'20'),(15,'30'),(20,'40'),(25,'50'),(30,'60'),(34,'60'),(35,'70'),(80,'70')])
def test_v4_band_boundaries_with_integral_band_are_preserved(payroll_v4, count, percent):
    r = calculate(Scenario(mode='real', personal_additions_regime='ade', ade_calculation='evaluations', ade_evaluations=count), payroll_v4)
    row = additions(r)['ADE']
    assert row['calculation']['rate'] == D(percent)/100
    assert row['calculation']['evaluations'] == count
    assert row['calculation']['method'] == 'evaluations'
    assert 'aproveitamento integral' in row['calculation']['assumption']


def test_entry_year_and_direct_evaluations_agree_and_export(client):
    base = {'mode':'real','personal_additions_regime':'ade_option','quinquennia':2,'health_enrolled':True}
    by_year = {**base,'ade_calculation':'entry_year','ade_entry_year':2021}
    by_count = {**base,'ade_calculation':'evaluations','ade_evaluations':5}
    year = client.post('/api/calculate',json=by_year).json()
    count = client.post('/api/calculate',json=by_count).json()
    # ADE: 3773.24 × 10% × (0,3×70 + 0,7×95)/100 = 330.16; bruto 7549.22-377.32+330.16=7502.06.
    # RPPS 771.0023+(7502.06-6251.37)×15%=958.61; IPSEMG 3,2%=240.07;
    # IR (7502.06-958.61)×27,5%-908.73=890.72; líquido 5412.66.
    assert year['monthly']['net'] == count['monthly']['net'] == '5412.66'
    assert additions(year)['ADE']['calculation']['entry_year'] == 2021
    assert additions(year)['ADE']['calculation']['evaluations'] == 5
    saved = client.post('/api/export/json',json=by_year).json()
    assert client.post('/api/calculate',json=saved['scenario']).json() == saved
    csv = client.post('/api/export/csv',json=by_year).text
    assert 'Avaliações satisfatórias: 5.' in csv and 'Ano de ingresso: 2021.' in csv
    next_year = client.post('/api/calculate',json={**by_year,'competence':'2026-01','ade_entry_year':2026}).json()
    assert additions(next_year)['ADE']['amount'] == '0.00'


@pytest.mark.parametrize('extra', [
    {'ade_calculation':'entry_year'},
    {'ade_calculation':'entry_year','ade_entry_year':2027},
    {'ade_calculation':'entry_year','ade_entry_year':2020.5},
    {'ade_calculation':'entry_year','ade_entry_year':2020,'ade_evaluations':6},
    {'ade_calculation':'evaluations'},
    {'ade_calculation':'evaluations','ade_evaluations':-1},
    {'ade_calculation':'evaluations','ade_evaluations':3.5},
    {'ade_calculation':'evaluations','ade_evaluations':5,'ade_percent':10},
])
def test_automatic_ade_rejects_ambiguous_or_invalid_inputs(client,extra):
    assert client.post('/api/calculate',json={'mode':'real','personal_additions_regime':'ade',**extra}).status_code == 422


@pytest.mark.parametrize('count,percent', [(0,'0'),(2,'0'),(3,'6'),(5,'10'),(10,'20'),(34,'60'),(35,'70'),(80,'70')])
def test_v5_band_is_the_ceiling_of_the_performance_index(payroll, count, percent):
    r = calculate(Scenario(mode='real', personal_additions_regime='ade', ade_calculation='evaluations', ade_evaluations=count, ade_adi='100'), payroll)
    c = additions(r)['ADE']['calculation']
    assert c['ceiling'] == D(percent) / 100
    # ADI 100 e AI 70: fator 0,3×0,70 + 0,7×1,00 = 0,91.
    assert c['factor'] == D('0.91')
    assert c['rate'] == D(percent) / 100 * D('0.91')


@pytest.mark.parametrize('ade_adi,amount', [
    (None, '330.16'),     # sem ADI própria: ADI da GDPI (95) → 3773.24×10%×0,875
    ('80', '290.54'),     # 3773.24×10%×(0,21+0,56)=290.539…
    ('70', '264.13'),     # 3773.24×10%×0,70=264.1268
    ('69.99', '0.00'),    # abaixo de 70: sem ADE no exercício
])
def test_ade_uses_its_own_adi_independent_of_gdpi(payroll, ade_adi, amount):
    s = Scenario(mode='real', personal_additions_regime='ade', ade_calculation='evaluations', ade_evaluations=5, ade_adi=ade_adi)
    r = calculate(s, payroll)
    row = additions(r)['ADE']
    assert row['amount'] == D(amount)
    assert row['calculation']['individual_origin'] == ('gdpi' if ade_adi is None else 'ade')
    # A GDPI continua usando a ADI própria dela, qualquer que seja a ADI do ADE.
    gdpi = lambda result: next(e for e in result['monthly']['earnings'] if e['name'] == 'GDPI')['amount']
    assert gdpi(r) == gdpi(calculate(Scenario(mode='real'), payroll))


def test_ade_adi_requires_automatic_ade(client):
    base = {'mode': 'real', 'personal_additions_regime': 'ade', 'ade_adi': '80'}
    assert client.post('/api/calculate', json={**base, 'ade_percent': '10'}).status_code == 422
    assert client.post('/api/calculate', json={**base, 'ade_calculation': 'evaluations', 'ade_evaluations': 5, 'ade_adi': '100.01'}).status_code == 422
    csv = client.post('/api/export/csv', json={**base, 'ade_calculation': 'evaluations', 'ade_evaluations': 5}).text
    assert ';ADE;290.54;' in csv and 'ADI: 80' in csv and 'AI: 70' in csv
