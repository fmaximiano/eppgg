from decimal import Decimal as D

import pytest
from pydantic import ValidationError
from app.calculator import calculate
from app.schemas import Scenario


@pytest.mark.parametrize('fields,total', [
    ({'cost_allowance_days': 20, 'cost_allowance_goals': '80'}, '1800.00'),
    ({'cost_allowance_days': 20, 'cost_allowance_goals': '0'}, '1000.00'),
    ({'cost_allowance_days': 20}, '1000.00'),
    ({'cost_allowance_days': 22, 'cost_allowance_daily': '73.45'}, '1615.90'),
    ({'cost_allowance_monthly': '1234.56'}, '1234.56'),
    ({'cost_allowance_monthly': '0'}, '0.00'),
])
def test_allowance_forms_and_incidence(parameters, fields, total):
    baseline = calculate(Scenario(), parameters)
    result = calculate(Scenario(**fields), parameters)
    row = next(r for r in result['monthly']['earnings'] if r['name'] == 'Ajuda de custo')
    assert row['amount'] == D(total)
    assert result['monthly']['net'] - baseline['monthly']['net'] == D(total)
    assert result['monthly']['bases'] == baseline['monthly']['bases']
    assert not any(row[key] for key in ['tax', 'pension', 'health', 'vacation', 'thirteenth'])
    assert result['annual']['thirteenth'] == baseline['annual']['thirteenth']
    assert result['annual']['net'] - baseline['annual']['net'] == 12 * D(total)


@pytest.mark.parametrize('fields', [
    {'cost_allowance_days': 20, 'cost_allowance_goals': 0, 'cost_allowance_daily': 50},
    {'cost_allowance_monthly': 100, 'cost_allowance_days': 20},
    {'cost_allowance_goals': 50}, {'cost_allowance_daily': 80},
    {'cost_allowance_days': -1}, {'cost_allowance_days': 32},
    {'cost_allowance_days': '1.5'}, {'cost_allowance_monthly': -1},
    {'cost_allowance_days': 20, 'cost_allowance_goals': 101},
])
def test_allowance_rejects_ambiguous_or_invalid_input(fields):
    with pytest.raises(ValidationError):
        Scenario(**fields)
