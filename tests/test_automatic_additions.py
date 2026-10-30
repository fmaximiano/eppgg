from decimal import Decimal as D

import pytest
from pydantic import ValidationError
from pathlib import Path
from app.calculator import calculate, money
from app.schemas import Scenario, Parameters


@pytest.mark.parametrize('quantity,count,names', [
    (0, None, []), (2, None, ['Quinquênio']),
    (0, 17, ['ADE']), (2, 17, ['Quinquênio', 'ADE']),
    (3, 17, ['Quinquênio']), (1, 5, ['Quinquênio']),
    (0, 0, ['ADE']),
])
@pytest.mark.parametrize('method', ['evaluations', 'entry_year'])
def test_automatic_additions(quantity, count, names, method):
    parameters = Parameters.model_validate_json((Path(__file__).parents[1] / 'data/payroll-2026-v7.json').read_text())
    fields = {'ade_evaluations': count} if method == 'evaluations' else {'ade_entry_year': None if count is None else 2026 - count}
    scenario = Scenario(mode='real', personal_additions_regime='auto', quinquennia=quantity,
                        ade_calculation=method, **fields)
    result = calculate(scenario, parameters)
    additions = [r for r in result['monthly']['earnings'] if r['name'] in ['Quinquênio', 'ADE']]
    assert [r['name'] for r in additions] == names
    if quantity:
        assert additions[0]['amount'] == money(D('3773.24') * D('.1') * quantity)
    if count == 17 and 'ADE' in names:
        assert additions[-1]['amount'] == D('1075.37')  # 3773.24 × 30% × 95%
    assert result['scenario']['personal_additions_regime'] == 'auto'
    assert result['scenario']['ade_calculation'] == method


@pytest.mark.parametrize('fields', [
    {'quinquennia': 4, 'ade_calculation': 'evaluations', 'ade_evaluations': 17},
    {'quinquennia': 4, 'ade_calculation': 'entry_year', 'ade_entry_year': 2009},
    {'quinquennia': 1, 'ade_calculation': 'evaluations', 'ade_evaluations': 0},
])
def test_excess_quinquennia_error(fields):
    with pytest.raises(ValidationError, match='superiores ao total de referência'):
        Scenario(personal_additions_regime='auto', **fields)


def test_invalid_automatic_inputs():
    with pytest.raises(ValidationError, match='posterior'):
        Scenario(personal_additions_regime='auto', ade_calculation='entry_year', ade_entry_year=2027)
    with pytest.raises(ValidationError):
        Scenario(personal_additions_regime='auto', ade_calculation='evaluations', ade_evaluations=5, ade_entry_year=2020)


def test_automatic_api_validation_and_roundtrip(client):
    fields = dict(mode='real', personal_additions_regime='auto', quinquennia=4,
                  ade_calculation='evaluations', ade_evaluations=17)
    response = client.post('/api/calculate', json=fields)
    assert response.status_code == 422
    assert 'total de referência (3)' in response.text
    fields['quinquennia'] = 3
    response = client.post('/api/calculate', json=fields)
    assert response.status_code == 200
    result = response.json()
    assert not any(r['name'] == 'ADE' for r in result['monthly']['earnings'])
    assert result['scenario']['ade_evaluations'] == 17
    replay = client.post('/api/calculate', json=result['scenario'])
    assert replay.json() == result
