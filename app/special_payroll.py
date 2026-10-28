"""Folhas específicas: RRA exclusivo e vínculos ativos no RPPS estadual."""
from datetime import date
from decimal import Decimal as D
from .calculator import CalculationError, calculate, health, income_tax, money
from .schemas import Parameters


def calculate_rra(r,p):
    if not isinstance(p,Parameters) or p.status!='verified':
        raise CalculationError('RRA exige tabela completa verificada do mês de pagamento.')
    if not p.valid_from<=date.fromisoformat(r.payment_competence+'-01')<=p.valid_until:
        raise CalculationError('Não há tabela vigente para o mês do pagamento RRA.')
    base=r.taxable_income-r.legal_expenses-r.official_pension-r.alimony
    # Multiplicar a tabela evita arredondar antecipadamente a renda mensal equivalente.
    band=next(b for b in p.tax_bands if b.upper is None or base<=b.upper*r.months)
    deduction=band.deduction*r.months
    tax=money(max(D(0),base*band.rate-deduction))
    gross=r.taxable_income+r.exempt_income
    payment=money(gross-r.official_pension-r.alimony-r.other_deductions-tax)
    return {'request':r.model_dump(mode='json'),'parameters':{'version':p.version,'source':p.sources.get('rra',p.sources['tax'])},
       'gross':money(gross),'taxable_income':r.taxable_income,'exempt_income':r.exempt_income,
       'base':money(base),'months':r.months,'equivalent_monthly_base':base/r.months,
       'rate':band.rate,'scaled_bracket_deduction':deduction,'income_tax':tax,
       'official_pension':r.official_pension,'alimony':r.alimony,'legal_expenses':r.legal_expenses,
       'other_deductions':r.other_deductions,'net_payment_before_legal_expenses':payment,
       'net_after_legal_expenses':money(payment-r.legal_expenses),
       'evidence':p.evidence,
       'warnings':['Tributação exclusiva de rendimentos de anos anteriores: tabela mensal multiplicada pelo número de meses, inclusive meses de 13º abrangidos pelo pagamento.',
          'Não aplica dependentes, desconto simplificado, redução mensal de 2026 nem dispensa de retenção até R$10.',
          'Contribuição oficial e pensão devem corresponder ao RRA. Despesas judiciais dedutíveis devem ser comprovadas, não indenizadas e proporcionais à parte tributável.',
          'Informe rendimentos isentos separadamente, conforme documento de pagamento. O sistema não concede isenção.',
          'Honorários são descontados no líquido após despesas; o valor anterior às despesas não afirma que honorários tenham sido retidos no crédito.',
          'Pagamentos parcelados devem usar o número de meses atribuído à parcela, conforme demonstrativo. Não mistura rendimentos do ano corrente nem simula opção pelo ajuste anual.']}


def consolidate_employments(request,p):
    if not isinstance(p,Parameters):
        raise CalculationError('Consolidação exige parâmetros completos de folha.')
    results=[]
    for e in request.employments:
        if e.scenario is not None:
            results.append(calculate(e.scenario,p))
        else:
            r=e.reported
            results.append({'monthly':{'gross':r.gross,'bases':{'tax':r.taxable_income,'health':r.ipsemg_base or D(0)},
               'pension':{'base':None,'amount':r.official_pension,'source':'Contribuição informada do contracheque'},
               'complementary':r.deductible_complementary,'alimony':r.alimony,
               'other_deductions':r.other_deductions,'health':{'copay':D(0)}}})

    def sheet(kind):
        leaves=[r['monthly'] if kind=='monthly' else r['annual'][kind] for r in results]
        # Saúde é única, sobre a maior remuneração estadual (Lei 25.143, art.6º, §8º).
        health_index=max(range(len(leaves)),key=lambda i:leaves[i]['bases']['health'])
        s=request.employments[0].scenario
        health_amount,health_rows=health(leaves[health_index]['bases']['health'],s,p,kind)
        groups={}
        rows=[]
        for i,(e,leaf) in enumerate(zip(request.employments,leaves)):
            key=' '.join(e.payer.casefold().split())
            groups.setdefault(key,[]).append(i)
            rows.append({'name':e.scenario.name if e.scenario else e.reported.name,'payer':e.payer,'gross':leaf['gross'],
               'pension':leaf['pension'],'complementary':leaf['complementary'],
               'alimony':leaf['alimony'],'other_deductions':leaf['other_deductions'],
               'copay':leaf['health']['copay'],'taxable_income':leaf['bases']['tax']})
        taxes=[]
        for key,indices in groups.items():
            income=sum((leaves[i]['bases']['tax'] for i in indices),D(0))
            legal=D(0)
            for i in indices:
                leaf=leaves[i]
                employment=request.employments[i]
                scenario=employment.scenario
                legal+=leaf['pension']['amount']
                if scenario is None or scenario.complementary_deductible:
                    legal+=leaf['complementary']
                deductible=scenario.alimony_deductible if scenario else employment.reported.alimony_deductible
                if deductible:
                    legal+=leaf['alimony']
            tax=income_tax(income,legal,request.employments[0].scenario.tax_dependents,p,exclusive=kind=='thirteenth')
            taxes.append({'payer':request.employments[indices[0]].payer,'employment_indices':indices,'income_tax':tax})
        gross=sum((l['gross'] for l in leaves),D(0))
        deductions=health_amount+sum((t['income_tax']['amount'] for t in taxes),D(0))
        deductions+=sum((l['pension']['amount']+l['complementary']+l['alimony']+l['other_deductions']+l['health']['copay'] for l in leaves),D(0))
        return {'kind':kind,'employments':rows,'income_tax_sources':taxes,
           'health':{'amount':health_amount,'base':leaves[health_index]['bases']['health'],
                     'employment_index':health_index,'beneficiaries':health_rows},
           'gross':money(gross),'deductions':money(deductions),'net':money(gross-deductions)}
    monthly=sheet('monthly')
    annual=None
    if request.employments[0].scenario.project_annual and all(e.scenario is not None for e in request.employments):
        vacation,thirteenth=sheet('vacation'),sheet('thirteenth')
        annual={'vacation':vacation,'thirteenth':thirteenth,
                'gross':money(11*monthly['gross']+vacation['gross']+thirteenth['gross']),
                'net':money(11*monthly['net']+vacation['net']+thirteenth['net']+10*sum((e['copay'] for e in monthly['employments']),D(0)))}
    return {'request':request.model_dump(mode='json'),'parameters':{'version':p.version,'status':p.status,'sources':p.sources},
            'monthly':monthly,'annual':annual,'evidence':p.evidence,
            'warnings':(['SIMULAÇÃO DEMONSTRATIVA — parâmetros fictícios, sem validade para folha.'] if p.status=='demo' else [])+['Cenários EPPGG calculam RPPS estadual. Outras fontes salariais usam bruto, rendimento tributável e contribuições efetivas informadas do contracheque; não se calcula sua previdência por uma tabela EPPGG.',
              'Acumulação legal informada pelo usuário; a simulação não autoriza acumular cargos. Comissão é parcela de um vínculo, não outro vínculo.',
              'RPPS é apurado por cargo. IPSEMG é cobrado uma vez sobre a maior remuneração estadual, com a mesma adesão/família em todos os vínculos.',
              'Identifique a mesma fonte pagadora com o mesmo nome: o IR soma seus rendimentos e aplica dependentes e simplificado uma vez por fonte. Fontes diferentes retêm separadamente.',
              'O líquido soma retenções mensais, não representa o imposto definitivo da declaração anual. Não compensa imposto já retido no mesmo mês.',
              'Coparticipação, pensão e consignações são valores efetivos de cada vínculo; não repita o mesmo desconto entre vínculos.',
              'Com fontes de contracheque, somente líquido mensal: não se repetem valores informados em férias/13º. Com todos os vínculos modelados, a projeção anual é estática, sem ajuste anual de IR.']}
