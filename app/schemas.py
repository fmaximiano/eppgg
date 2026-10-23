"""Contratos de entrada. Valores monetários trafegam como decimais, nunca float."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Position(StrictModel):
    level: str = Field(min_length=1, max_length=20)
    grade: str = Field(min_length=1, max_length=20)
    salary: Decimal = Field(gt=0)
    points: Decimal = Field(ge=0)


class PensionBand(StrictModel):
    upper: Decimal | None = Field(default=None, gt=0)
    rate: Decimal = Field(ge=0, le=1)


class TaxBand(StrictModel):
    upper: Decimal | None = Field(default=None, gt=0)
    rate: Decimal = Field(ge=0, le=1)
    deduction: Decimal = Field(ge=0)


class Commission(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0)
    kind: str = Field(min_length=1, max_length=80)
    allow_a: bool = False
    allow_b: bool = False
    a_keep_salary: bool = False
    a_keep_gdpi: bool = False
    b_keep_salary: bool = True
    b_keep_gdpi: bool = True
    optional_pension: bool = False
    mandatory_pension: bool = False
    pension_basis_a: Literal['paid', 'effective'] = 'paid'
    pension_basis_b: Literal['paid', 'effective'] = 'paid'
    pension_excess_only_a: bool = False
    health: bool = True
    tax: bool = True
    vacation: bool = True
    thirteenth: bool = True
    source: str = Field(min_length=1)

    @model_validator(mode='after')
    def pension_replacement_scope(self):
        if self.pension_excess_only_a and (self.a_keep_salary or self.pension_basis_a!='effective'):
            raise ValueError('Contribuição por excedente em A exige substituição do VB e base de referência do efetivo.')
        return self


class FunctionPayment(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0)
    kind: Literal['FGD', 'FGI', 'GTED', 'GTEI']
    requires_commission_kind: Literal['DAD', 'DAI'] | None = None
    allow_with_commission: bool = False
    optional_pension: bool = True
    tax: bool = True
    health: bool = True
    vacation: bool = True
    thirteenth: bool = True
    source: str = Field(min_length=1)


class HealthRules(StrictModel):
    rate: Decimal = Field(default=Decimal('.032'), ge=0, le=1)
    minimum: Decimal = Field(default=Decimal('60'), ge=0)
    maximum: Decimal = Field(default=Decimal('500'), gt=0)
    child_under21: Decimal = Field(default=Decimal('60'), ge=0)
    child_21_to38: Decimal = Field(default=Decimal('90'), ge=0)
    age_surcharge: Decimal = Field(default=Decimal('.01'), ge=0, le=1)
    surcharge_age: int = Field(default=60, ge=0, le=120)
    minimum_wage: Decimal = Field(gt=0)
    low_income_rule: Literal['unresolved', 'standard', 'statutory'] = 'unresolved'
    thirteenth_incidence: bool | None = None
    legal_exceptions: bool = False

    @model_validator(mode='after')
    def check_limits(self):
        if self.minimum > self.maximum:
            raise ValueError('Piso IPSEMG superior ao teto.')
        return self


class Parameters(StrictModel):
    version: str = Field(min_length=1, max_length=100)
    valid_from: date
    valid_until: date
    effective_competence: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    source: str = Field(min_length=1)
    status: Literal['demo', 'provisional', 'verified']
    verified_at: date | None = None
    notes: list[str] = Field(default_factory=list)
    sources: dict[str, str]
    positions: list[Position] = Field(min_length=1)
    gdpi_factor: Decimal = Field(ge=0)
    gdpi_point_share: Decimal = Field(default=Decimal('1'), gt=0, le=1)
    gdpi_reference_salary: Decimal = Field(gt=0)
    gdpi_min_adi: Decimal = Field(default=Decimal('70'), ge=0, le=100)
    gdpi_pension: bool
    gdpi_health: bool
    commissions: list[Commission] = Field(default_factory=list)
    functions: list[FunctionPayment] = Field(default_factory=list)
    pension_bands: list[PensionBand] = Field(min_length=1)
    rgps_ceiling: Decimal = Field(gt=0)
    health: HealthRules
    tax_bands: list[TaxBand] = Field(min_length=1)
    tax_dependent: Decimal = Field(ge=0)
    tax_simplified: Decimal = Field(ge=0)
    reduction_enabled: bool
    reduction_full_income: Decimal = Field(gt=0)
    reduction_full_max: Decimal = Field(ge=0)
    reduction_until: Decimal = Field(gt=0)
    reduction_intercept: Decimal = Field(ge=0)
    reduction_slope: Decimal = Field(ge=0)
    tax_withholding_minimum: Decimal = Field(default=Decimal('0'), ge=0)
    vacation_extra_pension: bool
    vacation_extra_health: bool
    career_rules: dict = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list)
    pension_revaluation: list[dict] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def coherent(self):
        if self.valid_until < self.valid_from:
            raise ValueError('Vigência inválida.')
        if self.status == 'verified' and not self.verified_at:
            raise ValueError('Parâmetros verificados exigem verified_at.')
        if not self.valid_from <= date.fromisoformat(self.effective_competence + '-01') <= self.valid_until:
            raise ValueError('Competência efetiva fora da vigência.')
        if len({(p.level, p.grade) for p in self.positions}) != len(self.positions):
            raise ValueError('Posição duplicada.')
        if len({c.code for c in self.commissions}) != len(self.commissions):
            raise ValueError('Cargo duplicado.')
        for bands in (self.pension_bands, self.tax_bands):
            limits = [b.upper for b in bands[:-1]]
            if bands[-1].upper is not None or any(v is None for v in limits):
                raise ValueError('Somente a última faixa deve ser ilimitada.')
            if limits != sorted(set(limits)):
                raise ValueError('Faixas devem ser crescentes e sem duplicatas.')
        for key in ('salary', 'gdpi', 'commission', 'pension', 'health', 'tax', 'vacation'):
            if not self.sources.get(key):
                raise ValueError(f'Fonte obrigatória: {key}.')
        if self.reduction_until <= self.reduction_full_income:
            raise ValueError('Limites da redução de IR inválidos.')
        return self


class CareerData(StrictModel):
    """Tabelas remuneratórias reais, independentes de parâmetros de descontos.

    Não completa campos ausentes com valores demonstrativos.
    """
    version: str = Field(min_length=1, max_length=100)
    valid_from: date
    valid_until: date
    effective_competence: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    source: str = Field(min_length=1)
    status: Literal['real'] = 'real'
    verified_at: date
    notes: list[str]
    sources: dict[str, str]
    positions: list[Position] = Field(min_length=50, max_length=50)
    gdpi_factor: Decimal = Field(gt=0)
    gdpi_reference_salary: Decimal = Field(gt=0)
    gdpi_point_share: Decimal = Field(gt=0, le=1)
    gdpi_min_adi: Decimal = Field(ge=0, le=100)
    gdpi_pension: bool = True
    gdpi_health: bool = True
    commissions: list[Commission]
    functions: list[FunctionPayment]
    career_rules: dict
    pending: list[str] = Field(min_length=1)
    evidence: list[dict] = Field(min_length=1)

    @model_validator(mode='after')
    def complete_matrix(self):
        expected={(level,grade) for level in ('I','II','III','IV','V') for grade in 'ABCDEFGHIJ'}
        if {(p.level,p.grade) for p in self.positions} != expected:
            raise ValueError('A matriz EPPGG real deve conter as 50 posições distintas de I-A a V-J.')
        reference=next(p.salary for p in self.positions if (p.level,p.grade)==('V','J'))
        if self.gdpi_reference_salary != reference:
            raise ValueError('VBref deve corresponder ao vencimento do último grau do último nível.')
        if self.valid_until < self.valid_from:
            raise ValueError('Vigência inválida.')
        codes=[p.code for p in self.commissions]+[p.code for p in self.functions]
        if len(codes)!=len(set(codes)):
            raise ValueError('Cargo/função duplicado.')
        return self


class Rubric(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(ge=0, le=10000000)
    nature: Literal['earning', 'deduction'] = 'earning'
    tax: bool = False
    pension: bool = False
    health: bool = False
    vacation: bool = False
    thirteenth: bool = False
    proportional: bool = False
    source: str = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def deduction_flags(self):
        if self.nature == 'deduction' and any((self.tax, self.pension, self.health, self.vacation, self.thirteenth)):
            raise ValueError('Consignações são pós-bases e não têm incidências.')
        return self


class Beneficiary(StrictModel):
    relationship: Literal['spouse', 'child', 'parent', 'sibling']
    age: int = Field(ge=0, le=120)
    special_condition: bool = False
    exemption_approved: bool = False
    eligibility_confirmed: bool = False

    @model_validator(mode='after')
    def exemption_scope(self):
        if self.exemption_approved and (self.relationship != 'child' or not self.special_condition):
            raise ValueError('Isenção especial exige filho/equiparado com condição especial e aprovação do IPSEMG.')
        return self


class Scenario(StrictModel):
    name: str = Field(default='Minha simulação', min_length=1, max_length=80)
    competence: str = Field(default='2026-10', pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    mode: Literal['demo', 'real', 'official'] = 'demo'
    level: str = Field(default='I', max_length=20)
    grade: str = Field(default='A', max_length=20)
    adi: Decimal = Field(default=Decimal('95'), ge=0, le=100)
    ai: Decimal = Field(default=Decimal('90'), ge=0, le=100)
    fraction: Decimal = Field(default=Decimal('1'), ge=0, le=1)
    gdpi_eligible: bool = True
    gdpi_evaluation: Literal['normal', 'no_institutional', 'statutory_70'] = 'normal'
    commission: str | None = None
    remuneration_option: Literal['none', 'a', 'b'] = 'none'
    commission_pension: bool = False
    function: str | None = None
    function_pension: bool = False
    capped_pension: bool = False
    complementary_rate: Decimal = Field(default=Decimal('0'), ge=0, le=Decimal('.3'))
    complementary_deductible: bool = False
    health_enrolled: bool = False
    age: int = Field(default=35, ge=0, le=120)
    beneficiaries: list[Beneficiary] = Field(default_factory=list, max_length=30)
    copay: Decimal = Field(default=Decimal('0'), ge=0, le=1000000)
    special_health: bool = False
    tax_dependents: int = Field(default=0, ge=0, le=30)
    alimony: Decimal = Field(default=Decimal('0'), ge=0, le=1000000)
    alimony_deductible: bool = False
    other_deductions: Decimal = Field(default=Decimal('0'), ge=0, le=1000000)
    rubrics: list[Rubric] = Field(default_factory=list, max_length=50)
    project_annual: bool = True

    @model_validator(mode='after')
    def choices(self):
        if self.remuneration_option != 'none' and not self.commission:
            raise ValueError('Selecione um cargo para a opção remuneratória.')
        if self.commission_pension and self.remuneration_option == 'none':
            raise ValueError('Contribuição facultativa requer opção comissionada.')
        if self.function_pension and not self.function:
            raise ValueError('Contribuição facultativa sobre função exige uma função selecionada.')
        if self.complementary_rate and not self.capped_pension:
            raise ValueError('Complementar exige regime limitado ao teto nesta simulação.')
        if not self.health_enrolled and (self.beneficiaries or self.copay or self.special_health):
            raise ValueError('Beneficiários e coparticipação exigem adesão ao IPSEMG.')
        return self


class CompareRequest(StrictModel):
    scenarios: list[Scenario] = Field(min_length=1, max_length=3)


class RetroRequest(StrictModel):
    entries: list[tuple[Scenario, Scenario]] = Field(min_length=1, max_length=60)
    treatment: Literal['competence_difference'] = 'competence_difference'


class RRARequest(StrictModel):
    payment_competence: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    mode: Literal['real', 'official'] = 'real'
    last_origin_year: int = Field(ge=1900, le=9998)
    months: Decimal = Field(ge=Decimal('.0001'), le=1200)
    taxable_income: Decimal = Field(gt=0, le=100000000)
    exempt_income: Decimal = Field(default=Decimal('0'), ge=0, le=100000000)
    official_pension: Decimal = Field(default=Decimal('0'), ge=0, le=100000000)
    alimony: Decimal = Field(default=Decimal('0'), ge=0, le=100000000)
    legal_expenses: Decimal = Field(default=Decimal('0'), ge=0, le=100000000)
    other_deductions: Decimal = Field(default=Decimal('0'), ge=0, le=100000000)

    @model_validator(mode='after')
    def prior_years_only(self):
        day=date.fromisoformat(self.payment_competence+'-01')
        if self.last_origin_year>=day.year:
            raise ValueError('RRA exclusivo exige rendimentos de anos anteriores ao pagamento. Separe valores do ano corrente.')
        if self.official_pension+self.alimony+self.legal_expenses>self.taxable_income:
            raise ValueError('Deduções do RRA não podem superar o rendimento tributável informado.')
        return self


class ReportedPayroll(StrictModel):
    name: str = Field(min_length=1,max_length=80)
    gross: Decimal = Field(ge=0,le=100000000)
    taxable_income: Decimal = Field(ge=0,le=100000000)
    official_pension: Decimal = Field(default=Decimal('0'),ge=0,le=100000000)
    deductible_complementary: Decimal = Field(default=Decimal('0'),ge=0,le=100000000)
    alimony: Decimal = Field(default=Decimal('0'),ge=0,le=100000000)
    alimony_deductible: bool = False
    other_deductions: Decimal = Field(default=Decimal('0'),ge=0,le=100000000)
    ipsemg_base: Decimal | None = Field(default=None,ge=0,le=100000000)

    @model_validator(mode='after')
    def taxable_portion(self):
        if self.taxable_income>self.gross:
            raise ValueError('Rendimento tributável informado não pode superar o bruto da fonte.')
        return self


class Employment(StrictModel):
    payer: str = Field(min_length=1, max_length=100)
    scenario: Scenario | None = None
    reported: ReportedPayroll | None = None

    @model_validator(mode='after')
    def one_kind(self):
        if (self.scenario is None)==(self.reported is None):
            raise ValueError('Informe cenário EPPGG ou valores do contracheque, uma única modalidade por vínculo.')
        return self


class MultipleEmploymentsRequest(StrictModel):
    employments: list[Employment] = Field(min_length=2, max_length=5)
    lawful_accumulation_confirmed: bool

    @model_validator(mode='after')
    def same_person_period(self):
        if not self.lawful_accumulation_confirmed:
            raise ValueError('Confirme que a acumulação dos vínculos é legalmente permitida.')
        first=self.employments[0].scenario
        if first is None:
            raise ValueError('O primeiro vínculo deve ser um cenário EPPGG de referência.')
        person_fields=('age','health_enrolled','beneficiaries','special_health','tax_dependents','project_annual')
        for employment in self.employments:
            s=employment.scenario
            if s is None:
                continue
            if s.competence!=first.competence or s.mode!=first.mode:
                raise ValueError('Os vínculos devem ter a mesma competência e modo.')
            if any(getattr(s,k)!=getattr(first,k) for k in person_fields):
                raise ValueError('Idade, adesão, família, dependentes fiscais e projeção anual devem ser iguais nos vínculos da mesma pessoa.')
        return self


class CareerRequest(StrictModel):
    scenario: Scenario
    future_level: str
    future_grade: str
    years: int = Field(default=5, ge=1, le=40)


class CareerActRequest(StrictModel):
    scenario: Scenario
    requirement_date: date
    protocol_date: date
    publication_date: date | None = None
    financial_date: date | None = None
    level_start: date
    probation_complete: bool
    satisfactory: bool
    in_effective_exercise: bool = True
    blocked_until: date | None = None
    progression_balance: Decimal = Field(ge=0, le=100000)
    promotion_balance: Decimal = Field(ge=0, le=100000)
    # Pontos homologados entram nos dois saldos; a concessão desconta apenas o saldo do ato.
    validated_event_points: Decimal = Field(default=Decimal('0'), ge=0, le=100000)
    prior_progressions_this_year: int = Field(default=0, ge=0, le=4)

    @model_validator(mode='after')
    def ordered_dates(self):
        if self.protocol_date < self.requirement_date:
            raise ValueError('Protocolo anterior à aquisição dos requisitos.')
        if self.publication_date and self.publication_date < self.protocol_date:
            raise ValueError('Publicação anterior ao protocolo.')
        if self.financial_date and not self.publication_date:
            raise ValueError('Vigência financeira exige data de publicação.')
        if self.level_start > self.requirement_date:
            raise ValueError('Início no nível posterior à aquisição de requisitos.')
        return self
