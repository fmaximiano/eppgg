"""Simulação de atos sobre saldos homologados; não homologa títulos ou documentos."""
from datetime import date
from .calculator import CalculationError, calculate, money


def project(request, parameters):
    current = calculate(request.scenario, parameters)
    future_scenario = request.scenario.model_copy(update={'level': request.future_level, 'grade': request.future_grade})
    future = calculate(future_scenario, parameters)
    delta = money(future['monthly']['net'] - current['monthly']['net']) if current['monthly']['net'] is not None and future['monthly']['net'] is not None else None
    annual_delta = money(future['annual']['net'] - current['annual']['net']) if current['annual'] and future['annual'] and current['annual']['net'] is not None and future['annual']['net'] is not None else None
    gross_delta=money(future['monthly']['gross']-current['monthly']['gross'])
    gross_annual_delta=money(future['annual']['gross']-current['annual']['gross']) if current['annual'] and future['annual'] else None
    return {'current': current, 'future': future, 'monthly_difference': delta, 'annual_difference': annual_delta,
            'gross_monthly_difference':gross_delta,'gross_annual_difference':gross_annual_delta,
            'series': [{'year': i, 'current': current['annual']['net'] if current['annual'] else None,
                        'future': future['annual']['net'] if future['annual'] else None,
                        'accumulated_gross_difference':money(gross_annual_delta*i) if gross_annual_delta is not None else None,
                        'accumulated_difference': money(annual_delta * i) if annual_delta is not None else None}
                       for i in range(1, request.years + 1)],
            'assumptions': 'Mudança imediata para posição selecionada; valores constantes, sem atos automáticos ou reajustes futuros.'}


def simulate_act(r, p):
    rules = p.career_rules
    required = ('progression_cost', 'promotion_cost', 'interstice_years', 'level_order', 'grade_order', 'annual_progression_limits', 'source')
    if not all(k in rules for k in required):
        raise CalculationError('Regras de desenvolvimento funcional não cadastradas.')
    if r.financial_date and r.financial_date.strftime('%Y-%m') != r.scenario.competence:
        raise CalculationError('Use a competência da vigência financeira para selecionar a matriz do ato.')
    if not r.probation_complete or not r.satisfactory or not r.in_effective_exercise:
        raise CalculationError('Ato impedido: confira estágio probatório, avaliação satisfatória e efetivo exercício.')
    if r.blocked_until and r.protocol_date <= r.blocked_until:
        raise CalculationError('Impedimento funcional vigente na data do protocolo.')
    position = next((x for x in p.positions if (x.level, x.grade) == (r.scenario.level, r.scenario.grade)), None)
    if position is None:
        raise CalculationError('Posição atual não cadastrada.')
    levels, grades = rules['level_order'], rules['grade_order']
    if position.level not in levels or position.grade not in grades:
        raise CalculationError('Posição não coberta pelas regras de desenvolvimento.')
    # Decimais são construídos a partir de texto, inclusive quando vieram do JSON administrativo.
    from decimal import Decimal
    progression = r.progression_balance + r.validated_event_points
    promotion = r.promotion_balance + r.validated_event_points
    pc, mc = Decimal(str(rules['progression_cost'])), Decimal(str(rules['promotion_cost']))
    if pc <= 0 or mc <= 0:
        raise CalculationError('Custos de desenvolvimento inválidos.')
    anniversary_year = r.level_start.year + int(rules['interstice_years'])
    try:
        anniversary = r.level_start.replace(year=anniversary_year)
    except ValueError:
        anniversary = date(anniversary_year, 2, 28)
    check_date = r.financial_date or r.requirement_date
    idx = levels.index(position.level)
    target, act, used = position, 'none', Decimal('0')
    if promotion >= mc and idx < len(levels) - 1 and check_date >= anniversary:
        candidates = [x for x in p.positions if x.level == levels[idx + 1] and x.salary > position.salary]
        if not candidates:
            raise CalculationError('Próximo nível sem grau com vencimento superior cadastrado.')
        target = min(candidates, key=lambda x: grades.index(x.grade))
        promotion -= mc
        act, used = 'promotion', mc
    else:
        limit = int(rules['annual_progression_limits'].get(position.level, 0))
        available = max(0, limit - r.prior_progressions_this_year)
        count = min(int(progression // pc), available, len(grades) - 1 - grades.index(position.grade))
        if count:
            target_grade = grades[grades.index(position.grade) + count]
            target = next((x for x in p.positions if x.level == position.level and x.grade == target_grade), None)
            if target is None:
                raise CalculationError('Grau futuro ausente da matriz salarial.')
            used = pc * count
            progression -= used
            act = 'progression'
    return {'act': act, 'target': {'level': target.level, 'grade': target.grade}, 'points_used': used,
            'progression_balance': progression, 'promotion_balance': promotion,
            'interstice_completed_on': anniversary, 'requirement_date': r.requirement_date,
            'protocol_date': r.protocol_date, 'publication_date': r.publication_date, 'financial_date': r.financial_date,
            'source': rules['source'], 'status': p.status,
            'warning': 'Estimativa sobre pontos já homologados. Não valida títulos, janelas de requerimento, afastamentos ou atos administrativos; sem publicação/vigência não há efeito financeiro automático.'}
