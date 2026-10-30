"""Motor decimal independente de HTTP/banco; nunca extrapola tabelas ausentes."""
from decimal import Decimal, ROUND_HALF_UP
from .schemas import Parameters, Scenario, CareerData

D = Decimal
ZERO = D('0')


class CalculationError(ValueError):
    pass


def money(value):
    return D(value).quantize(D('.01'), rounding=ROUND_HALF_UP)


def progressive(base, bands):
    lower, total, memory = ZERO, ZERO, []
    for band in bands:
        taxable = max(ZERO, min(base, band.upper if band.upper is not None else base) - lower)
        contribution = taxable * band.rate
        memory.append({'from': lower, 'until': band.upper, 'base': taxable,
                       'rate': band.rate, 'amount_unrounded': contribution})
        total += contribution
        if band.upper is None or base <= band.upper:
            break
        lower = band.upper
    return money(total), memory


def income_tax(income, legal_deductions, dependents, p, *, exclusive=False):
    legal = legal_deductions + dependents * p.tax_dependent
    deduction = max(legal, p.tax_simplified)
    base = max(ZERO, income - deduction)
    band = next(b for b in p.tax_bands if b.upper is None or base <= b.upper)
    before = money(max(ZERO, base * band.rate - band.deduction))
    reduction = ZERO
    if p.reduction_enabled:
        if income <= p.reduction_full_income:
            reduction = min(before, p.reduction_full_max)
        elif income <= p.reduction_until:
            reduction = min(before, money(max(ZERO, p.reduction_intercept - p.reduction_slope * income)))
    calculated=money(before-reduction)
    waived=not exclusive and ZERO<calculated<=p.tax_withholding_minimum
    amount=ZERO if waived else calculated
    return {'income': money(income), 'legal_deductions': money(legal),
            'simplified_deduction': p.tax_simplified, 'deduction': money(deduction),
            'method': 'legal' if legal >= p.tax_simplified else 'simplified',
            'base': money(base), 'rate': band.rate, 'bracket_deduction': band.deduction,
            'before_reduction': before, 'reduction': reduction,'calculated_amount':calculated,
            'waiver_applied':waived,'waiver_amount':calculated-amount,
            'minimum_withholding':p.tax_withholding_minimum,'exclusive':exclusive,'amount':money(amount)}


def health(base, s, p, payroll='monthly'):
    h = p.health
    if not s.health_enrolled:
        return ZERO, []
    if payroll == 'thirteenth':
        if h.thirteenth_incidence is None:
            raise CalculationError('Incidência IPSEMG no 13º ainda não cadastrada. Desative projeção anual ou cadastre a regra.')
        if not h.thirteenth_incidence:
            return ZERO, []
    if h.legal_exceptions:
        return statutory_health(base,s,h)
    if s.special_health or any(b.special_condition for b in s.beneficiaries):
        raise CalculationError('IPSEMG: invalidez, deficiência e doenças raras exigem regra específica ainda não implementada.')
    if base <= 2 * h.minimum_wage and h.low_income_rule == 'unresolved':
        raise CalculationError('IPSEMG: tratamento até dois salários mínimos pendente nesta versão de parâmetros.')
    if sum(b.relationship == 'spouse' for b in s.beneficiaries) > 1:
        raise CalculationError('IPSEMG: apenas um cônjuge/companheiro pode ser simulado.')
    if any(b.relationship == 'child' and b.age > 38 for b in s.beneficiaries):
        raise CalculationError('IPSEMG: filho acima de 38 anos exige enquadramento específico.')
    if any(b.relationship in ('parent', 'sibling') for b in s.beneficiaries):
        raise CalculationError('IPSEMG: elegibilidade/acumulação de pais e irmãos depende de regra específica; cálculo bloqueado.')

    def percentage(age):
        return money(min(h.maximum, max(h.minimum, base * (h.rate + (h.age_surcharge if age >= h.surcharge_age else ZERO)))))

    children = sum(b.relationship == 'child' and b.age < 21 for b in s.beneficiaries)
    titular = percentage(s.age)
    combined = min(h.maximum, titular + children * h.child_under21)
    rows = [{'name': 'Titular + filhos menores de 21 (teto conjunto)', 'amount': money(combined),
             'titular': titular, 'children': children, 'maximum': h.maximum}]
    for b in s.beneficiaries:
        if b.relationship == 'child' and b.age < 21:
            continue
        amount = h.child_21_to38 if b.relationship == 'child' else percentage(b.age)
        rows.append({'name': 'Filho de 21 a 38' if b.relationship == 'child' else 'Cônjuge/companheiro', 'amount': money(amount)})
    return money(sum((r['amount'] for r in rows), ZERO)), rows


def statutory_health(base, s, h):
    """Lei 25.143/2025, arts.4º e 6º; Decreto 48.981/2025, arts.4º–5º."""
    if s.special_health:
        raise CalculationError('Condição especial do titular exige análise própria; a isenção automática prevista aqui é para filho com isenção aprovada pelo IPSEMG.')
    beneficiaries=s.beneficiaries
    relationships={b.relationship for b in beneficiaries}
    if sum(b.relationship=='spouse' for b in beneficiaries)>1:
        raise CalculationError('IPSEMG: apenas um cônjuge/companheiro pode ser informado.')
    if sum(b.relationship=='parent' for b in beneficiaries)>2:
        raise CalculationError('IPSEMG: podem ser informados no máximo dois pais.')
    if 'parent' in relationships and relationships & {'spouse','child','sibling'}:
        raise CalculationError('IPSEMG: pais não podem ser acumulados com cônjuge, filhos ou irmãos neste enquadramento.')
    if 'sibling' in relationships and relationships & {'spouse','child','parent'}:
        raise CalculationError('IPSEMG: irmãos não podem ser acumulados com cônjuge, filhos ou pais.')
    for b in beneficiaries:
        if b.relationship in ('parent','sibling') and not b.eligibility_confirmed:
            raise CalculationError('IPSEMG: confirme elegibilidade e dependência econômica para pais/irmãos.')
        if b.relationship in ('child','sibling') and b.age>=39 and not b.special_condition:
            raise CalculationError('IPSEMG: filho/irmão a partir de 39 anos exige enquadramento especial comprovado.')
        if b.relationship=='child' and b.special_condition and not b.exemption_approved:
            raise CalculationError('IPSEMG: a isenção do filho com condição especial deve estar aprovada pelo Instituto.')

    low_income=base <= 2*h.minimum_wage and h.low_income_rule=='statutory'
    if low_income:
        # Sem piso e sem adicional etário; filhos <21 isentos e 21–38 com teto próprio.
        rows=[{'name':'Titular · até dois salários mínimos','amount':money(base*h.rate)}]
        for b in beneficiaries:
            if b.relationship=='child':
                amount=ZERO if b.exemption_approved or b.age<21 else money(min(base*h.rate,h.child_21_to38))
            else:
                amount=money(base*h.rate)
            rows.append({'name':beneficiary_label(b)+' · regra de baixa renda','amount':amount})
        return money(sum((r['amount'] for r in rows),ZERO)),rows

    def percentage(age):
        regular=money(min(h.maximum,max(h.minimum,base*h.rate)))
        additional=money(min(h.maximum,base*h.age_surcharge)) if age>=h.surcharge_age else ZERO
        return regular,additional

    children=sum(b.relationship=='child' and b.age<21 and not b.exemption_approved for b in beneficiaries)
    titular,additional=percentage(s.age)
    combined=money(min(h.maximum,titular+children*h.child_under21)+additional)
    rows=[{'name':'Titular + filhos menores de 21 (teto conjunto)','amount':combined,
           'titular':titular,'age_additional':additional,'children':children,'maximum':h.maximum}]
    for b in beneficiaries:
        if b.relationship=='child':
            if b.exemption_approved:
                rows.append({'name':'Filho/equiparado · isenção aprovada IPSEMG','amount':ZERO})
            elif b.age>=21:
                rows.append({'name':'Filho de 21 a 38 anos','amount':h.child_21_to38})
        else:
            regular,additional=percentage(b.age)
            rows.append({'name':beneficiary_label(b),'amount':regular+additional,'regular':regular,'age_additional':additional})
    return money(sum((r['amount'] for r in rows),ZERO)),rows


def beneficiary_label(b):
    return {'child':'Filho/equiparado','spouse':'Cônjuge/companheiro','parent':'Pai/mãe','sibling':'Irmão/irmã'}[b.relationship]


def earning(name, amount, source, *, tax=True, pension=True, health=True, vacation=True, thirteenth=True):
    return {'name': name, 'amount': money(amount), 'source': source, 'tax': tax, 'pension': pension,
            'health': health, 'vacation': vacation, 'thirteenth': thirteenth}


def personal_additions(s, p, salary):
    """Direitos reconhecidos no vínculo; não concede tempo nem homologa ADE.

    As simulações por avaliações usam a faixa integral, com avaliações satisfatórias.
    O percentual informado é preservado somente para cenários anteriores.
    Bases informadas são integrais e só depois recebem a fração do mês.
    """
    if s.personal_additions_regime == 'auto':
        count = s.personal_additions_count()
        include_ade = not s.quinquennia or (count is not None and s.quinquennia < count // 5)
        if not include_ade or (count is None and s.ade_calculation != 'granted_percentage'):
            s = s.model_copy(update={'personal_additions_regime': 'quinquennium' if s.quinquennia else 'ade',
                                     'ade_calculation': 'granted_percentage', 'ade_percent': ZERO,
                                     'ade_entry_year': None, 'ade_evaluations': None, 'ade_adi': None})
        else:
            s = s.model_copy(update={'personal_additions_regime': 'ade_option' if s.quinquennia else 'ade'})
    automatic_ade = s.ade_calculation != 'granted_percentage'
    if not (s.quinquennia or s.ade_percent or automatic_ade):
        return []
    rules = getattr(p, 'personal_additions_rules', {})
    if not rules:
        raise CalculationError('Não há regras de quinquênio e ADE cadastradas nesta versão de parâmetros.')
    evaluations = performance = None
    ade_rate = s.ade_percent / 100
    if automatic_ade:
        if rules.ade_method not in ('satisfactory_evaluations', 'performance_index', 'individual_index'):
            raise CalculationError('Cálculo do ADE por avaliações não disponível nesta versão de parâmetros.')
        evaluations = int(s.competence[:4]) - s.ade_entry_year if s.ade_calculation == 'entry_year' else s.ade_evaluations
        ade_rate = max((c.rate for c in rules.ade_reference_ceilings if evaluations >= c.evaluations), default=ZERO)
        if rules.ade_method in ('performance_index', 'individual_index'):
            # Índice ADE = P × [(0,3 × AI) + (0,7 × ADI)]; sem avaliação institucional, P × ADI.
            # ADI abaixo do mínimo não gera ADE no exercício.
            individual = s.adi if s.ade_adi is None else s.ade_adi
            institutional = rules.ade_institutional_score if rules.ade_method == 'performance_index' else None
            performance = {
                'ceiling': ade_rate, 'individual': individual,
                'individual_origin': 'gdpi' if s.ade_adi is None else 'ade',
                'institutional': institutional,
                'factor': (individual if institutional is None else
                           rules.ade_institutional_weight * institutional + rules.ade_individual_weight * individual) / 100,
                'eligible': individual >= rules.ade_min_individual,
            }
            ade_rate = ade_rate * performance['factor'] if performance['eligible'] else ZERO
    if ade_rate > rules.ade_max_rate:
        raise CalculationError('Percentual do ADE superior ao máximo cadastrado para a competência.')
    rows = []
    for name, quantity, rate, informed_base, source_key in (
        ('Quinquênio', s.quinquennia, rules.quinquennium_rate * s.quinquennia, s.quinquennium_base, 'quinquennium'),
        ('ADE', None, ade_rate, s.ade_base, 'ade'),
    ):
        if not rate and not (name == 'ADE' and automatic_ade):
            continue
        base = salary if informed_base is None else informed_base
        item = earning(name, base * rate * s.fraction, p.sources[source_key])
        item['calculation'] = {
            'base': base, 'base_origin': 'effective_salary' if informed_base is None else 'recognized_base',
            'rate': rate, 'quantity': quantity, 'fraction': s.fraction,
            'regime': s.personal_additions_regime,
            'method': 'recognized_quinquennia' if name == 'Quinquênio' else s.ade_calculation,
        }
        if name == 'ADE' and automatic_ade and performance and performance['institutional'] is None:
            item['calculation'].update(evaluations=evaluations, entry_year=s.ade_entry_year, **performance,
                assumption=('Índice ADE = faixa × ADI: sem avaliação institucional, considera-se integralmente a ADI '
                            '(Decreto 44.503/2007, art. 4º, § 8º, redação do Decreto 46.756/2015). ADI da última avaliação '
                            f'concluída até 1º de outubro{"" if s.ade_adi is not None else " (não informada: usada a ADI da GDPI)"}; '
                            f'abaixo de {rules.ade_min_individual} não há ADE no exercício. '
                            'Quantidade de avaliações satisfatórias por número informado ou pelo ano da competência menos o de ingresso.'))
        elif name == 'ADE' and automatic_ade and performance:
            item['calculation'].update(evaluations=evaluations, entry_year=s.ade_entry_year, **performance,
                assumption=(f'Índice ADE = faixa × ({rules.ade_institutional_weight} × AI + {rules.ade_individual_weight} × ADI). '
                            f'AI {rules.ade_institutional_score}: órgão sem Acordo de Resultados. ADI da última avaliação concluída até 1º de outubro'
                            f'{"" if s.ade_adi is not None else " (não informada: usada a ADI da GDPI)"}; '
                            f'abaixo de {rules.ade_min_individual} não há ADE no exercício. '
                            'Quantidade de avaliações satisfatórias por número informado ou pelo ano da competência menos o de ingresso.'))
        elif name == 'ADE' and automatic_ade:
            item['calculation'].update(evaluations=evaluations, entry_year=s.ade_entry_year,
                assumption='Avaliações anuais satisfatórias e aproveitamento integral da faixa. Ano de ingresso: diferença entre o ano da competência e o ingresso.')
        rows.append(item)
    return rows


def earnings(s, p):
    pos = next((v for v in p.positions if (v.level, v.grade) == (s.level, s.grade)), None)
    if pos is None:
        raise CalculationError('Nível/grau não cadastrado nesta competência; não se presume fator de progressão.')
    adi, ai = s.adi, s.ai
    if s.gdpi_evaluation == 'statutory_70':
        adi, ai = D('70'), D('70')
    evaluation = adi / 100 if s.gdpi_evaluation == 'no_institutional' else (D('.6') * adi + D('.4') * ai) / 100
    raw_ceiling = pos.points * p.gdpi_point_share * p.gdpi_factor * p.gdpi_reference_salary * s.fraction
    ceiling = money(raw_ceiling)
    gdpi = money(raw_ceiling * evaluation) if s.gdpi_eligible and adi >= p.gdpi_min_adi else ZERO
    keep_salary, keep_gdpi = True, True
    commission = None
    if s.remuneration_option != 'none':
        commission = next((c for c in p.commissions if c.code == s.commission), None)
        if commission is None:
            raise CalculationError('Cargo comissionado não cadastrado para a competência.')
        option = s.remuneration_option
        if not getattr(commission, 'allow_' + option):
            if s.mode=='real' and option=='a':
                raise CalculationError('Opção A real ainda não habilitada: confira a manutenção das parcelas no enquadramento concreto.')
            raise CalculationError('Opção remuneratória não permitida para este cargo.')
        keep_salary = getattr(commission, option + '_keep_salary')
        keep_gdpi = getattr(commission, option + '_keep_gdpi')
        if s.commission_pension and not commission.optional_pension:
            raise CalculationError('Contribuição facultativa não permitida para este cargo.')
    rows = []
    if keep_salary:
        rows.append(earning('Vencimento básico', pos.salary * s.fraction, p.sources['salary']))
    if keep_gdpi:
        rows.append(earning('GDPI', gdpi, p.sources['gdpi'], pension=p.gdpi_pension, health=p.gdpi_health))
    if commission:
        rows.append(earning(commission.code + (' integral' if s.remuneration_option == 'a' else ' · 50%'),
                            commission.amount * s.fraction * (1 if s.remuneration_option == 'a' else D('.5')),
                            commission.source, pension=s.commission_pension or commission.mandatory_pension, tax=commission.tax,
                            health=commission.health, vacation=commission.vacation, thirteenth=commission.thirteenth))
    if s.function:
        function=next((f for f in p.functions if f.code==s.function),None)
        if function is None:
            raise CalculationError('Função/gratificação não cadastrada para a competência.')
        if function.requires_commission_kind and (not commission or commission.kind!=function.requires_commission_kind):
            raise CalculationError(f'{function.code} exige cargo {function.requires_commission_kind} em exercício.')
        if commission and not function.allow_with_commission:
            raise CalculationError('Combinação de função gratificada com cargo comissionado não habilitada neste cadastro.')
        if s.function_pension and not function.optional_pension:
            raise CalculationError('Contribuição facultativa sobre a função não habilitada.')
        rows.append(earning(function.code+' · integral',function.amount*s.fraction,function.source,
                            pension=s.function_pension,tax=function.tax,health=function.health,
                            vacation=function.vacation,thirteenth=function.thirteenth))
    rows.extend(personal_additions(s, p, pos.salary))
    allowance = s.cost_allowance_monthly
    if allowance is None and s.cost_allowance_days is not None:
        daily = s.cost_allowance_daily
        if daily is None:
            daily = D('50') * (1 + (s.cost_allowance_goals or ZERO) / 100)
        allowance = daily * s.cost_allowance_days
    if allowance is not None:
        rows.append(earning('Ajuda de custo', allowance, 'Dias, metas ou valor informados pelo usuário',
                            tax=False, pension=False, health=False, vacation=False, thirteenth=False))

    for r in s.rubrics:
        if r.nature == 'earning':
            rows.append(earning(r.name, r.amount * (s.fraction if r.proportional else 1), r.source,
                                **{k: getattr(r, k) for k in ('tax', 'pension', 'health', 'vacation', 'thirteenth')}))
    reference_pension = ZERO
    if commission and getattr(commission, 'pension_basis_' + s.remuneration_option) == 'effective':
        # Base do cargo efetivo pode subsistir mesmo quando sua remuneração não é paga.
        if not keep_salary:
            reference_pension += money(pos.salary * s.fraction)
        if not keep_gdpi and p.gdpi_pension:
            reference_pension += gdpi
        if s.remuneration_option=='a' and commission.pension_excess_only_a and (s.commission_pension or commission.mandatory_pension):
            # A substitui o VB: a opção contributiva acrescenta somente o excedente,
            # sem somar VB de referência + vencimento integral da comissão.
            reference_pension -= min(money(pos.salary*s.fraction),money(commission.amount*s.fraction))
    return rows, {'points': pos.points, 'factor': p.gdpi_factor, 'reference_salary': p.gdpi_reference_salary,
                  'point_share':p.gdpi_point_share,'effective_points':pos.points*p.gdpi_point_share,
                  'evaluation': evaluation, 'ceiling': ceiling, 'actual': gdpi if keep_gdpi else ZERO,
                  'minimum_adi': p.gdpi_min_adi, 'eligible': s.gdpi_eligible and adi >= p.gdpi_min_adi,
                  'evaluation_mode': s.gdpi_evaluation, 'effective_adi': adi, 'effective_ai': ai,
                  'formula': 'P_tabela × quota legal × F × VBref × avaliação × proporção'}, reference_pension


def payroll(rows, s, p, kind='monthly', reference_pension=ZERO):
    if kind == 'thirteenth':
        rows = [r.copy() for r in rows if r['thirteenth']]
    elif kind == 'vacation':
        extra = [earning('1/3 férias · ' + r['name'], r['amount'] / 3, p.sources['vacation'],
                         tax=r['tax'], pension=r['pension'] and p.vacation_extra_pension,
                         health=r['health'] and p.vacation_extra_health) for r in rows if r['vacation']]
        rows = [r.copy() for r in rows] + extra
    gross = money(sum((r['amount'] for r in rows), ZERO))
    bases = {k: money(sum((r['amount'] for r in rows if r[k]), ZERO)) for k in ('tax', 'pension', 'health')}
    bases['pension'] += reference_pension
    pension_base = min(bases['pension'], p.rgps_ceiling) if s.capped_pension else bases['pension']
    pension, bands = progressive(pension_base, p.pension_bands)
    complement = money(max(ZERO, bases['pension'] - p.rgps_ceiling) * s.complementary_rate) if s.capped_pension else ZERO
    ipsemg, health_rows = health(bases['health'], s, p, kind)
    alimony = s.alimony
    legal = pension + (complement if s.complementary_deductible else ZERO) + (alimony if s.alimony_deductible else ZERO)
    tax = income_tax(bases['tax'], legal, s.tax_dependents, p,exclusive=kind=='thirteenth')
    # Consignações mensais não se repetem no 13º; coparticipação vale apenas para o mês selecionado.
    other = s.other_deductions + sum((money(r.amount * (s.fraction if r.proportional else 1)) for r in s.rubrics if r.nature == 'deduction'), ZERO) if kind != 'thirteenth' else ZERO
    copay = s.copay if kind == 'monthly' else ZERO
    deductions = money(pension + complement + ipsemg + tax['amount'] + alimony + other + copay)
    return {'kind': kind, 'earnings': rows, 'gross': gross, 'deductions': deductions,
            'net': money(gross - deductions), 'bases': bases,
            'pension': {'base': pension_base, 'amount': pension, 'bands': bands, 'capped': s.capped_pension,
                        'effective_reference_addition': reference_pension},
            'complementary': complement, 'health': {'amount': ipsemg, 'beneficiaries': health_rows, 'copay': copay},
            'income_tax': tax, 'alimony': alimony, 'other_deductions': money(other)}


def calculate(s: Scenario, p: Parameters | CareerData):
    from datetime import date
    competence = date.fromisoformat(s.competence + '-01')
    if not p.valid_from <= competence <= p.valid_until:
        raise CalculationError('Não há parâmetros vigentes para a competência.')
    if s.mode == 'official' and p.status != 'verified':
        raise CalculationError('Não há parâmetros oficiais auditados para esta competência.')
    rows, gdpi, reference_pension = earnings(s, p)
    if isinstance(p,CareerData):
        return calculate_compensation(s,p,rows,gdpi)
    monthly = payroll(rows, s, p, reference_pension=reference_pension)
    warnings = list(p.notes)
    if p.status != 'verified':
        warnings.insert(0, 'SIMULAÇÃO DEMONSTRATIVA — valores e incidências não validados para folha de pagamento.' if p.status == 'demo' else 'SIMULAÇÃO PROVISÓRIA — parâmetros aguardam auditoria.')
    warnings.append('Uma fonte pagadora, mês completo conforme proporção e vínculo ativo. Exceções de GDPI devem ter enquadramento validado; esta tela não concede direitos.')
    if s.alimony:
        warnings.append('Pensão informada em valor fixo por folha; reflexos em férias e 13º dependem do título judicial.')
    annual = None
    if s.project_annual:
        thirteenth = payroll(rows, s, p, 'thirteenth', reference_pension)
        vacation = payroll(rows, s, p, 'vacation', reference_pension)
        annual = {'thirteenth': thirteenth, 'vacation': vacation,
                  'vacation_increment_net': money(vacation['net'] - monthly['net'] - monthly['health']['copay']),
                  'gross': money(11 * monthly['gross'] + vacation['gross'] + thirteenth['gross']),
                  'net': money(11 * monthly['net'] + vacation['net'] + thirteenth['net'] + 10 * monthly['health']['copay']),
                  'assumptions': 'Projeção estática: 11 folhas normais + 1 folha de férias com terço + 13º integral; mesmas regras e remuneração, sem reajustes. Coparticipação informada apenas no mês selecionado, descontada uma vez no total anual. Não é o total efetivo do ano civil.'}
        warnings.append('Férias/13º: incidências seguem o cadastro; projeção estática exige 12/12 avos. Benefícios não recorrentes devem ser ajustados em cenários separados.')
    return {'scenario': s.model_dump(mode='json'), 'parameters': {
        'version': p.version, 'status': p.status, 'valid_from': p.valid_from, 'valid_until': p.valid_until,
        'effective_competence': p.effective_competence, 'verified_at': p.verified_at,
        'source': p.source, 'sources': p.sources}, 'rounding': 'Decimal, ROUND_HALF_UP, centavos por rubrica e por tributo; RPPS arredondado após soma das faixas.',
        'monthly': monthly, 'gdpi': gdpi, 'annual': annual, 'warnings': warnings,
        'pending':p.pending,'evidence':p.evidence,'pension_revaluation':p.pension_revaluation}


def calculate_compensation(s,p,rows,gdpi):
    """Exibe somente os valores confirmados, sem estimar descontos com fixtures."""
    gross=money(sum((r['amount'] for r in rows),ZERO))
    annual=None
    if s.project_annual:
        thirteenth=money(sum((r['amount'] for r in rows if r['thirteenth']),ZERO))
        extra=money(sum((money(r['amount']/3) for r in rows if r['vacation']),ZERO))
        vacation=money(gross+extra)
        annual={'gross':money(12*gross+extra+thirteenth),'net':None,
                'thirteenth':{'gross':thirteenth,'net':None},'vacation':{'gross':vacation,'net':None},
                'assumptions':'Projeção bruta estática: 12 remunerações, terço e 13º integral, sem reajustes ou avos proporcionais; descontos não apurados.'}
    return {'scenario':s.model_dump(mode='json'),'parameters':{
        k:getattr(p,k) for k in ('version','status','valid_from','valid_until','effective_competence','verified_at','source','sources')},
        'rounding':'Decimal, ROUND_HALF_UP, centavos por rubrica.',
        'monthly':{'kind':'monthly','earnings':rows,'gross':gross,'deductions':None,'net':None},
        'gdpi':gdpi,'annual':annual,'pending':p.pending,
        'warnings':p.notes+['DADOS REMUNERATÓRIOS REAIS — descontos e líquido não calculados; não se misturam faixas demonstrativas às tabelas oficiais.']}
