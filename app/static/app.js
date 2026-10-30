'use strict';
const $ = (s, node = document) => node.querySelector(s);
const $$ = (s, node = document) => [...node.querySelectorAll(s)];
const form = $('#scenario-form');
const escape = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const currencyFormatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const numberFormatter = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
const currency = (n) =>
  n == null
    ? '—'
    : currencyFormatter.format(Number(n));
const number = (n) => numberFormatter.format(Number(n));
const field = (name) => form.elements.namedItem(name);
// Notas em campos de texto: aceitam vírgula ou ponto (ex.: 95,5) e são enviadas com ponto.
const decimal = (value) => String(value).trim().replace(',', '.');
function validateDecimals() {
  for (const input of $$('[data-decimal]')) {
    const value = decimal(input.value);
    const valid =
      value === '' ||
      (/^\d{1,3}(\.\d{1,2})?$/.test(value) && Number(value) <= Number(input.dataset.decimal));
    input.setCustomValidity(
      valid
        ? ''
        : `Informe um número entre 0 e ${input.dataset.decimal}, com até duas casas decimais.`,
    );
  }
}
let params = null,
  lastResult = null,
  generation = 0,
  timer,
  toastTimer,
  editingIndex = null;
let calculationController = null;
let calculationBusy = false,
  previousEvaluation = 'no_institutional',
  manualGrades = { adi: '95', ai: '' };
let saved = [];
try {
  const value = JSON.parse(localStorage.getItem('eppgg.scenarios.v1') || '[]');
  if (Array.isArray(value))
    saved = value
      .slice(0, 3)
      .filter(
        (s) =>
          s && typeof s === 'object' && !Array.isArray(s) && ['real', 'official'].includes(s.mode),
      );
} catch {
  /* corrupt local storage is never executed */
}

// Competências em português: o <input type="month"> segue o idioma do navegador. O campo
// original continua com o valor AAAA-MM (escondido), sincronizado com dois selects.
const MONTHS = [
  'Janeiro',
  'Fevereiro',
  'Março',
  'Abril',
  'Maio',
  'Junho',
  'Julho',
  'Agosto',
  'Setembro',
  'Outubro',
  'Novembro',
  'Dezembro',
];
function monthPicker(input) {
  const native = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  const label = input.closest('label')?.firstChild.textContent.trim() || 'Competência';
  const month = document.createElement('select');
  const year = document.createElement('select');
  month.className = 'month-picker-month';
  year.className = 'month-picker-year';
  month.setAttribute('aria-label', `${label}: mês`);
  year.setAttribute('aria-label', `${label}: ano`);
  month.append(...MONTHS.map((name, i) => new Option(name, String(i + 1).padStart(2, '0'))));
  const last = Math.max(new Date().getFullYear(), Number(input.value.slice(0, 4))) + 2;
  for (let y = last; y >= 2000; y--) year.append(new Option(y, y));
  const wrapper = document.createElement('span');
  wrapper.className = 'month-picker';
  wrapper.append(month, year);
  input.type = 'hidden';
  input.after(wrapper);
  const sync = () => {
    [year.value, month.value] = native.get.call(input).split('-');
  };
  // Atribuições feitas pelo código (cenário carregado, por exemplo) também atualizam os selects.
  Object.defineProperty(input, 'value', {
    get: () => native.get.call(input),
    set: (value) => {
      native.set.call(input, value);
      sync();
    },
  });
  for (const select of [month, year]) {
    select.addEventListener('input', (event) => event.stopPropagation());
    select.addEventListener('change', (event) => {
      event.stopPropagation();
      native.set.call(input, `${year.value}-${month.value}`);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }
  input.form?.addEventListener('reset', () => setTimeout(sync));
  sync();
}
$$('input[type=month]').forEach(monthPicker);

function updateThemeButton() {
  const dark = document.documentElement.dataset.theme === 'dark';
  $('#theme-toggle').setAttribute('aria-label', dark ? 'Usar tema claro' : 'Usar tema escuro');
  $('#theme-toggle').title = dark ? 'Usar tema claro' : 'Usar tema escuro';
}
$('#theme-toggle').addEventListener('click', () => {
  window.toggleTheme();
  updateThemeButton();
});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateThemeButton);
updateThemeButton();

function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.add('hidden'), 4200);
}
async function api(path, body, signal) {
  const response = await fetch(
    path,
    body === undefined
      ? { signal }
      : {
          signal,
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = 'O serviço não respondeu. Tente novamente.';
    }
    if (Array.isArray(detail))
      detail = detail
        .map((x) => {
          const names = {
            months: 'Número de meses',
            taxable_income: 'Rendimento tributável',
            last_origin_year: 'Ano de origem',
            payment_competence: 'Mês do pagamento',
            official_pension: 'Contribuição previdenciária',
            legal_expenses: 'Despesas judiciais',
            alimony: 'Pensão alimentícia',
            employments: 'Vínculos',
            payer: 'Fonte pagadora',
            beneficiaries: 'Beneficiários',
            age: 'Idade',
            competence: 'Competência',
            adi: 'Avaliação individual',
            ai: 'Avaliação institucional',
          };
          const key = x.loc?.filter((v) => typeof v === 'string').slice(-1)[0];
          const message =
            x.type === 'value_error'
              ? x.msg.replace(/^Value error, /, '')
              : x.type === 'missing'
                ? 'Preencha este dado.'
                : 'Confira o valor informado.';
          return `${names[key] || 'Dados da simulação'}: ${message}`;
        })
        .join(' · ');
    if (
      typeof detail === 'string' &&
      /Nenhuma tabela|Nenhuma.*cadastrada|Nenhum catálogo/.test(detail)
    )
      detail = 'Não há valores disponíveis para a competência selecionada.';
    throw new Error(typeof detail === 'string' ? detail : 'Não foi possível concluir a operação.');
  }
  return response.json();
}
function showTab(id) {
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === id));
  $$('.tab').forEach((t) => {
    t.classList.toggle('active', t.dataset.tab === id);
    if (t.dataset.tab === id) t.setAttribute('aria-current', 'page');
    else t.removeAttribute('aria-current');
  });
  history.replaceState(null, '', id === 'calculator' ? location.pathname : '#' + id);
  document.dispatchEvent(new CustomEvent('tab:shown', { detail: id }));
  updateNetBar();
  if (id === 'sources') return loadSources();
  if (id === 'compare') renderSaved();
}
$$('.tab').forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));
document.addEventListener('click', (event) => {
  const target = event.target.closest('[data-goto]');
  if (target) showTab(target.dataset.goto);
});
// Avisa outras áreas (como os cenários hipotéticos) que o cenário da Calculadora mudou.
function announceScenario() {
  updateFormHints();
  updateNetBar();
  document.dispatchEvent(new CustomEvent('scenario:updated', { detail: lastResult }));
}

// Resumo do que está preenchido em cada seção recolhível do formulário.
function updateFormHints() {
  const value = (name) => Number(field(name).value || 0);
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const hints = {
    pension: [
      field('capped_pension').checked ? 'Teto do RGPS' : 'RPPS sem teto',
      value('complementary_percent')
        ? `complementar ${number(value('complementary_percent'))}%`
        : '',
      field('commission_pension').checked && !field('commission_pension').disabled
        ? 'inclui comissão'
        : '',
    ],
    health: field('age').value === '' ? 'Sem contribuição' : plural($$('.beneficiary').filter((div) => $('.relationship', div).value).length, 'beneficiário', 'beneficiários'),
    tax: [
      value('tax_dependents')
        ? plural(value('tax_dependents'), 'dependente', 'dependentes')
        : 'Sem dependentes',
      value('alimony') ? `pensão ${currency(value('alimony'))}` : '',
      value('other_deductions') ? `outros ${currency(value('other_deductions'))}` : '',
    ],
    rubrics: [
      value('fraction') === 100 ? 'Mês integral' : `${number(value('fraction'))}% do mês`,
      $$('#rubrics .rubric').length
        ? plural($$('#rubrics .rubric').length, 'rubrica', 'rubricas')
        : '',
    ],
  };
  for (const [key, hint] of Object.entries(hints))
    $(`[data-hint="${key}"]`).textContent = [hint].flat().filter(Boolean).join(' · ');
}
form.addEventListener('input', updateFormHints);
form.addEventListener('change', updateFormHints);

// No celular, mantém o líquido à vista enquanto o resultado está fora da tela.
let resultInView = false;
function updateNetBar() {
  const visible =
    Boolean(lastResult?.monthly) && $('#calculator').classList.contains('active') && !resultInView;
  $('#net-bar').hidden = !visible;
  document.body.classList.toggle('has-net-bar', visible);
  if (visible) $('#net-bar-value').textContent = currency(lastResult.monthly.net);
}
new IntersectionObserver((entries) => {
  resultInView = entries[0].isIntersecting;
  updateNetBar();
}).observe($('.output-panel'));
$('#net-bar-link').addEventListener('click', () => $('#result').scrollIntoView({ block: 'start' }));

function options(select, values, old) {
  select.replaceChildren(...values.map((v) => new Option(v, v)));
  if (values.includes(old)) select.value = old;
}
function positionOptions(levelId, gradeId) {
  const levels = [...new Set((params?.positions || []).map((p) => p.level))];
  const level = $(levelId),
    grade = $(gradeId),
    old = level.value;
  options(level, levels, old);
  updateGrades(levelId, gradeId);
}
function updateGrades(levelId, gradeId) {
  const level = $(levelId),
    grade = $(gradeId);
  options(
    grade,
    (params?.positions || []).filter((p) => p.level === level.value).map((p) => p.grade),
    grade.value,
  );
}
async function loadParameters() {
  clearTimeout(timer);
  calculationController?.abort();
  const request = ++generation;
  params = null;
  lastResult = null;
  calculationBusy = false;
  updateControls();
  $$('[data-family]').forEach((select) => (select.disabled = true));
  field('remuneration_option').disabled = true;
  $('#compare-options').disabled = true;
  $('#result').replaceChildren();
  $('#version-label').textContent = 'Consultando valores da carreira…';
  try {
    const data = await api(
      `/api/parameters?competence=${encodeURIComponent(field('competence').value)}&mode=${encodeURIComponent(field('mode').value)}`,
    );
    if (request !== generation) return;
    params = data;
    positionOptions('#level', '#grade');
    positionOptions('#future-level', '#future-grade');
    for (const family of ['DAD', 'GTED', 'DAI', 'GTEI', 'FGD', 'FGI']) {
      const rows = [...data.commissions, ...(data.functions || [])].filter(
        (item) => item.kind === family,
      );
      const select = $('#' + family.toLowerCase());
      select.replaceChildren(
        new Option(['DAD', 'DAI'].includes(family) ? 'Sem ' + family : 'Nenhuma', ''),
        ...rows.map((item) => new Option(`${item.code} · ${currency(item.amount)}`, item.code)),
      );
    }
    if (!data.commissions.some((item) => item.code === field('commission').value)) {
      field('commission').value = '';
      field('remuneration_option').value = 'none';
    }
    if (!(data.functions || []).some((item) => item.code === field('function').value))
      field('function').value = '';
    updateControls();
    $('#version-label').textContent =
      `Valores aplicáveis de ${dateLabel(data.valid_from)} a ${dateLabel(data.valid_until)}`;

    $('#calculation-error').classList.add('hidden');
    await calculate();
  } catch (error) {
    if (request !== generation) return;
    $('#version-label').textContent = 'Nenhuma tabela disponível';
    $('#level').replaceChildren();
    $('#grade').replaceChildren();
    $('#future-level').replaceChildren();
    $('#future-grade').replaceChildren();
    showCalculationError(error);
    updateControls();
    announceScenario();
  }
}
// Lei 25.143/2025, art. 4º, §§ 2º–3º: pais e irmãos são grupos exclusivos.
function compatibleBeneficiaryRelationships(except = null) {
  const others = $$('.beneficiary').filter((div) => div !== except);
  const relationships = others.map((div) => $('.relationship', div).value).filter(Boolean);
  return ['child', 'spouse', 'parent', 'sibling'].filter((relationship) => {
    if (relationship === 'parent')
      return relationships.every((r) => r === 'parent') && relationships.length < 2;
    if (relationship === 'sibling') return relationships.every((r) => r === 'sibling');
    return relationships.every((r) => ['child', 'spouse'].includes(r) && r !== relationship);
  });
}
function beneficiaryRow(value) {
  if (!value) value = { relationship: '', age: '', special_condition: false };
  const div = document.createElement('div');
  div.className = 'mini-panel beneficiary';
  div.innerHTML = `<div class="beneficiary-main"><label class="beneficiary-relationship">Beneficiário<select class="relationship"><option value="">Nenhum</option><option value="child">Filho(a)</option><option value="spouse">Cônjuge</option><option value="parent">Pai/mãe</option><option value="sibling">Irmão(ã)</option></select></label><label class="beneficiary-age-field">Idade<input class="beneficiary-age" type="number" min="0" max="120" value="${escape(value.age)}" required></label></div><div class="beneficiary-fields"><label class="check"><input type="checkbox" class="special-condition" ${value.special_condition ? 'checked' : ''}> Condição especial</label></div><button type="button" class="text-button remove">Remover beneficiário</button>`;
  $('.relationship', div).value = value.relationship;
  $('.remove', div).addEventListener('click', () => {
    div.remove();
    schedule();
  });
  $('#beneficiaries').append(div);
  $$('.beneficiary').forEach(updateBeneficiaryControls);
}
$('#add-beneficiary').addEventListener('click', () => {
  if ($$('.beneficiary').length >= 30 || !compatibleBeneficiaryRelationships().length) return;
  beneficiaryRow();
  schedule();
});
function rubricRow(
  value = {
    name: '',
    amount: '0',
    nature: 'earning',
    source: 'Informado pelo usuário; incidências a conferir',
    tax: false,
    pension: false,
    health: false,
    vacation: false,
    thirteenth: false,
    proportional: false,
  },
) {
  const div = document.createElement('div');
  div.className = 'mini-panel rubric';
  div.innerHTML = `<label>Rubrica<input class="rubric-name-input" value="${escape(value.name)}" maxlength="100" required></label><div class="field-row"><label>Valor (R$)<input class="rubric-amount" type="number" min="0" step="0.01" value="${escape(value.amount)}" required></label><label>Natureza<select class="rubric-nature"><option value="earning">Provento</option><option value="deduction">Consignação</option></select></label></div><div class="flag-grid">${[
    ['tax', 'IR'],
    ['pension', 'RPPS'],
    ['health', 'IPSEMG'],
    ['vacation', 'Férias'],
    ['thirteenth', '13º'],
    ['proportional', 'Proporcional'],
  ]
    .map(
      ([key, label]) =>
        `<label class="check"><input type="checkbox" data-flag="${key}" ${value[key] ? 'checked' : ''}>${label}</label>`,
    )
    .join(
      '',
    )}</div><button type="button" class="text-button remove">Remover rubrica</button>`;
  div.dataset.source = value.source || 'Informado pelo usuário; incidências a conferir';
  $('.rubric-nature', div).value = value.nature;
  $('.remove', div).addEventListener('click', () => {
    div.remove();
    schedule();
  });
  $('#rubrics').append(div);
  updateRubricControls(div);
}
$('#add-rubric').addEventListener('click', () => {
  if ($$('.rubric').length >= 50) return toast('Limite de 50 rubricas.');
  rubricRow();
});
function scenario() {
  const s = {};
  for (const name of [
    'name',
    'competence',
    'mode',
    'level',
    'grade',
    'adi',
    'ai',
    'fraction',
    'gdpi_evaluation',
    'remuneration_option',
    'copay',
    'alimony',
    'other_deductions',
  ])
    s[name] = field(name).value;
  for (const name of [
    'gdpi_eligible',
    'commission_pension',
    'function_pension',
    'capped_pension',
    'complementary_deductible',
    'project_annual',
  ])
    s[name] = field(name).checked;
  const automatic = s.gdpi_evaluation === 'statutory_70';
  s.adi = automatic ? '70' : s.gdpi_eligible ? decimal(field('adi').value) || '0' : '0';
  s.ai = automatic
    ? '70'
    : s.gdpi_eligible && s.gdpi_evaluation === 'normal'
      ? decimal(field('ai').value) || '0'
      : '0';
  for (const name of ['copay', 'alimony', 'other_deductions']) s[name] ||= '0';
  s.alimony_deductible = Number(s.alimony) > 0;
  s.health_enrolled = field('age').value !== '';
  if (!s.health_enrolled) s.copay = '0';
  s.special_health = false;
  if (!s.capped_pension) {
    s.complementary_deductible = false;
  }
  s.age = s.health_enrolled ? Number(field('age').value) : 35;
  s.tax_dependents = Number(field('tax_dependents').value);
  s.commission = field('commission').value || null;
  s.function = field('function').value || null;
  s.fraction = String(Number(field('fraction').value) / 100);
  s.personal_additions_regime = 'auto';
  s.quinquennia = field('quinquennia').disabled ? 0 : Number(field('quinquennia').value);
  s.ade_calculation = field('ade_calculation').disabled
    ? 'granted_percentage'
    : field('ade_calculation').value;
  s.ade_percent =
    s.ade_calculation === 'granted_percentage' && !field('ade_calculation').disabled
      ? field('ade_percent').value
      : '0';
  for (const name of ['ade_entry_year', 'ade_evaluations'])
    s[name] = field(name).disabled || field(name).value === '' ? null : Number(field(name).value);
  for (const name of ['cost_allowance_days', 'cost_allowance_goals', 'cost_allowance_monthly', 'cost_allowance_daily'])
    s[name] = field(name).disabled || field(name).value === '' ? null : decimal(field(name).value);
  // O percentual inicial não inclui ajuda de custo enquanto os dias não forem informados.
  if (s.cost_allowance_days === null && s.cost_allowance_goals === '100')
    s.cost_allowance_goals = null;
  s.quinquennium_base = null;
  s.ade_base = null;
  s.ade_adi =
    field('ade_adi').disabled || !field('ade_adi').value ? null : decimal(field('ade_adi').value);
  s.complementary_rate = s.capped_pension
    ? String(Number(field('complementary_percent').value) / 100)
    : '0';
  s.beneficiaries = (s.health_enrolled ? $$('.beneficiary') : []).filter((div) => $('.relationship', div).value).map((div) => ({
    relationship: $('.relationship', div).value,
    age: Number($('.beneficiary-age', div).value),
    special_condition: $('.special-condition', div).checked,
    exemption_approved: $('.relationship', div).value === 'child' && $('.special-condition', div).checked,
    eligibility_confirmed: ['parent', 'sibling'].includes($('.relationship', div).value),
  }));
  s.rubrics = $$('.rubric').map((div) => ({
    name: $('.rubric-name-input', div).value,
    amount: $('.rubric-amount', div).value,
    nature: $('.rubric-nature', div).value,
    source: div.dataset.source,
    ...Object.fromEntries($$('[data-flag]', div).map((i) => [i.dataset.flag, i.checked])),
  }));
  return s;
}
function schedule() {
  calculationController?.abort();
  if (params) {
    generation++;
    calculationBusy = false;
  }
  lastResult = null;
  updateControls();
  clearTimeout(timer);
  if (!form.checkValidity()) {
    $('#result').innerHTML =
      '<div class="empty panel">Preencha os campos indicados para atualizar a simulação.</div>';
    announceScenario();
    return;
  }
  timer = setTimeout(() => {
    if (params) calculate();
  }, 400);
}
form.addEventListener('input', (event) => {
  if (
    !event.target.dataset.family &&
    !['competence', 'mode', 'level', 'grade'].includes(event.target.name)
  )
    schedule();
});
form.addEventListener('change', (event) => {
  const family = event.target.dataset.family;
  if (!family && !['competence', 'mode', 'level', 'grade'].includes(event.target.name)) return;
  if (family) {
    if (['DAD', 'DAI'].includes(family)) {
      field('commission').value = event.target.value;
      const cargo = params?.commissions.find((item) => item.code === event.target.value);
      if (!cargo) field('remuneration_option').value = 'none';
      else if (field('remuneration_option').value === 'none')
        field('remuneration_option').value = cargo.allow_b ? 'b' : 'a';
    } else field('function').value = event.target.value;
    updateCommissionChoices();
  }
  if (event.target.name === 'remuneration_option') updateCommissionChoices();
  if (['competence', 'mode'].includes(event.target.name)) loadParameters();
  else if (event.target.name === 'level') {
    updateGrades('#level', '#grade');
    schedule();
  } else schedule();
});
form.addEventListener('submit', (event) => {
  event.preventDefault();
  clearTimeout(timer);
  calculate();
});
$('#future-level').addEventListener('change', () => {
  updateGrades('#future-level', '#future-grade');
  updateActions();
});
function showCalculationError(error) {
  $('#calculation-error').textContent = error.message;
  $('#calculation-error').classList.remove('hidden');
  $('#result').innerHTML =
    '<div class="empty panel">Confira os dados indicados para obter uma nova simulação.</div>';
  lastResult = null;
}
async function calculate() {
  if (!params || !form.checkValidity()) return;
  clearTimeout(timer);
  calculationController?.abort();
  const controller = new AbortController();
  calculationController = controller;
  const timeout = setTimeout(() => controller.abort(), 15000);
  const request = ++generation;
  calculationBusy = true;
  updateActions();
  try {
    const result = await api('/api/calculate', scenario(), controller.signal);
    if (request !== generation) return;
    lastResult = result;
    $('#calculation-error').classList.add('hidden');
    renderResult(result);
  } catch (error) {
    if (request === generation)
      showCalculationError(controller.signal.aborted
        ? new Error('O cálculo demorou demais. Altere um campo para tentar novamente.')
        : error);
  } finally {
    clearTimeout(timeout);
    if (request === generation) {
      calculationBusy = false;
      updateActions();
      announceScenario();
    }
  }
}
function metric(label, value) {
  return `<div class="metric-row"><span>${escape(label)}</span><strong>${escape(value)}</strong></div>`;
}
function renderResult(r) {
  if (r.parameters.status === 'real') return renderRealResult(r);
  const m = r.monthly,
    t = m.income_tax,
    g = r.gdpi;
  const row = (name, amount, source, negative = false, incidence = '') =>
    `<tr><td><span class="rubric-name">${escape(name)}</span>${source ? `<span class="source-small">${escape(source)}</span>` : ''}${incidence ? `<span class="incidences">${escape(incidence)}</span>` : ''}</td><td class="amount ${negative ? 'deduction' : ''}">${negative ? '− ' : ''}${currency(amount)}</td></tr>`;
  const rows = m.earnings
    .map((e) =>
      row(
        e.name,
        e.amount,
        earningReference(e),
        false,
        [
          e.tax ? 'IR' : '',
          e.pension ? 'RPPS' : '',
          e.health ? 'IPSEMG' : '',
          e.vacation ? 'Férias' : '',
          e.thirteenth ? '13º' : '',
        ]
          .filter(Boolean)
          .join(' · '),
      ),
    )
    .join('');
  const deductions = [
    ['RPPS · contribuição progressiva', m.pension.amount, 'Lei Complementar nº 64/2002'],
    ['Previdência complementar', m.complementary, 'Percentual informado sobre o excedente ao teto'],
    ['IPSEMG Saúde', m.health.amount, 'Lei nº 25.143/2025 · Decreto nº 48.981/2025'],
    ['Coparticipação IPSEMG', m.health.copay, 'Valor informado'],
    ['IRRF', t.amount, 'Tabela e redução do imposto de renda de 2026'],
    [
      'Pensão alimentícia',
      m.alimony,
      'Valor informado por folha; dedução condicionada ao enquadramento',
    ],
    [
      'Outros descontos e consignações',
      m.other_deductions,
      'Valores informados após as bases legais',
    ],
  ]
    .filter(([, value]) => Number(value) !== 0)
    .map(([name, value, source]) => row(name, value, source, true))
    .join('');
  const annual = r.annual;
  $('#result').innerHTML =
    `<div class="summary-grid"><div class="stat"><span class="stat-label"><i class="dot"></i> Remuneração bruta</span><span class="stat-value">${currency(m.gross)}</span><span class="stat-sub">Proventos da competência</span></div><div class="stat"><span class="stat-label"><i class="dot gold"></i> Descontos totais</span><span class="stat-value">${currency(m.deductions)}</span><span class="stat-sub">Contribuições e deduções</span></div><div class="stat net"><span class="stat-label">Seu líquido mensal</span><span class="stat-value">${currency(m.net)}</span><span class="stat-sub">Estimativa ${r.parameters.status === 'demo' ? 'demonstrativa' : 'da competência'}</span></div></div>
+  <div class="panel"><div class="result-title"><div><h2>Seu demonstrativo</h2><p>${escape(r.scenario.name)} · ${escape(r.scenario.competence)} · Nível ${escape(r.scenario.level)}, grau ${escape(r.scenario.grade)}</p></div><span class="pill ${r.parameters.status === 'verified' ? 'verified' : ''}">ESTIMATIVA</span></div><div class="table-scroll"><table><thead><tr><th>RUBRICA / FUNDAMENTO</th><th>VALOR MENSAL</th></tr></thead><tbody>${rows}${deductions}<tr class="total-row"><td>Líquido estimado</td><td class="amount">${currency(m.net)}</td></tr></tbody></table></div><div class="export-bar"><span>Guarde seu demonstrativo e os dados da simulação.</span><div class="actions"><button class="secondary export" data-format="csv">↓ Baixar planilha</button><button class="secondary export" data-format="json">↓ Guardar simulação</button></div></div></div>
+  <div class="subgrid"><div class="panel"><div class="small-title">DESEMPENHO & PRODUTIVIDADE</div><h2>Sua GDPI em detalhe</h2><div class="big-inline">${currency(g.actual)}</div>${metric('Fator de avaliação', number(Number(g.evaluation) * 100) + '%')}${metric('Teto com notas de 100%', currency(g.ceiling))}${metric('Pontos × fator × vencimento de referência', `${number(g.effective_points ?? g.points)} × ${g.factor} × ${currency(g.reference_salary)}`)}<p class="field-help">Pontos variáveis × fator legal × vencimento de referência × avaliação × proporção do mês.</p>${!g.eligible ? '<div class="callout">GDPI zerada: elegibilidade ou nota mínima individual não atendida.</div>' : ''}</div><div class="panel"><div class="small-title">OLHANDO PARA O ANO</div><h2>Além do salário mensal</h2>${annual ? `<div class="big-inline">${currency(annual.net)}</div><p class="field-help">Estimativa anual com remuneração constante</p>${metric('13º líquido (folha separada)', currency(annual.thirteenth.net))}${metric('Férias + terço · líquido da folha', currency(annual.vacation.net))}${metric('Diferença líquida da folha de férias', currency(annual.vacation_increment_net))}<p class="field-help">11 remunerações mensais, uma folha de férias com terço e o 13º integral. Coparticipação descontada uma única vez no ano.</p>` : '<p>Projeção anual desativada neste cenário.</p>'}</div></div>
+  <div class="panel breakdown"><h2>Por dentro dos descontos</h2><details><summary>Previdência · base ${currency(m.pension.base)}</summary>${metric('Remuneração contributiva antes do teto', currency(m.bases.pension))}${Number(m.pension.effective_reference_addition) ? metric('Base do efetivo mantida sem pagamento', currency(m.pension.effective_reference_addition)) : ''}${m.pension.bands.map((b) => metric(`${currency(b.from)} a ${b.until == null ? 'sem limite' : currency(b.until)} · ${number(Number(b.rate) * 100)}%`, `${currency(b.base)} × ${number(Number(b.rate) * 100)}%`)).join('')}${metric('Contribuição após soma das faixas', currency(m.pension.amount))}${r.pension_revaluation?.length ? `<p class="field-help">Limites recompostos anualmente conforme LC 64/2002, art.28, §5º; a atualização de cada ano aparece abaixo.</p>${r.pension_revaluation.map((y) => metric(String(y.year) + ' · reajuste ' + number(Number(y.index) * 100) + '%', y.upper_limits.map(currency).join(' / '))).join('')}` : ''}</details><details><summary>Imposto de renda · ${t.method === 'legal' ? 'deduções legais' : 'desconto simplificado'} mais vantajoso</summary>${metric('Rendimento tributável (referência da redução)', currency(t.income))}${metric('Deduções legais', currency(t.legal_deductions))}${metric('Simplificado disponível', currency(t.simplified_deduction))}${metric('Dedução escolhida', currency(t.deduction))}${metric('Base após deduções', currency(t.base))}${metric('Alíquota / parcela a deduzir', `${number(Number(t.rate) * 100)}% / ${currency(t.bracket_deduction)}`)}${metric('IR pela tabela', currency(t.before_reduction))}${metric('Redução legal', currency(t.reduction))}${t.waiver_applied ? metric('Dispensa de retenção até R$10', currency(t.waiver_amount)) : ''}${metric('IRRF', currency(t.amount))}<div class="callout">A redução considera o rendimento tributável antes das deduções. IPSEMG Saúde não reduz a base mensal do IR.</div></details><details><summary>IPSEMG · base ${currency(m.bases.health)}</summary>${m.health.beneficiaries.map((b) => metric(b.name, currency(b.amount))).join('')}${!m.health.beneficiaries.length ? '<p class="field-help">Sem desconto de assistência nesta folha.</p>' : ''}</details>${annual ? `<details><summary>Memória das folhas de férias e 13º</summary>${['vacation', 'thirteenth'].map((k) => `<h3>${k === 'vacation' ? 'Férias com terço' : '13º separado'}</h3>${metric('Bruto', currency(annual[k].gross))}${metric('RPPS', currency(annual[k].pension.amount))}${metric('IPSEMG', currency(annual[k].health.amount))}${metric('IRRF desta folha', currency(annual[k].income_tax.amount))}${metric('Demais descontos', currency(Number(annual[k].deductions) - Number(annual[k].pension.amount) - Number(annual[k].health.amount) - Number(annual[k].income_tax.amount)))}${metric('Líquido', currency(annual[k].net))}`).join('')}<p class="field-help">Confira os valores considerados em cada folha antes de planejar suas despesas.</p></details>` : ''}<details><summary>Condições da estimativa</summary>${metric('Vigência', `${dateLabel(r.parameters.valid_from)} a ${dateLabel(r.parameters.valid_until)}`)}<p class="field-help">Os valores são arredondados para centavos por parcela e desconto. A contribuição previdenciária é arredondada após a soma das faixas.</p><ul class="warning-list">${calculationNotes(
      r,
    )
      .map((w) => `<li>${escape(w)}</li>`)
      .join('')}</ul></details></div>`.replace(/^\+/gm, '');
  $$('.export').forEach((b) => b.addEventListener('click', () => exportResult(b.dataset.format)));
}
async function exportResult(kind) {
  if (!lastResult) return toast('Calcule um cenário válido antes de exportar.');
  try {
    const response = await fetch('/api/export/' + kind, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lastResult.scenario),
    });
    if (!response.ok) throw new Error('Não foi possível exportar. Recalcule e tente novamente.');
    download(await response.blob(), 'eppgg-memoria.' + kind);
  } catch (error) {
    toast(error.message);
  }
}
function download(blob, name) {
  const url = URL.createObjectURL(blob),
    a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function persist() {
  try {
    localStorage.setItem('eppgg.scenarios.v1', JSON.stringify(saved));
  } catch {
    toast(
      'O navegador não permitiu gravar cenários. Guarde a simulação em arquivo para recuperá-la depois.',
    );
  }
  renderSaved();
}
$('#save').addEventListener('click', async () => {
  if (saved.length >= 3 && editingIndex === null)
    return toast('Você já tem três cenários. Exclua um para salvar outro.');
  try {
    const s = scenario();
    await api('/api/calculate', s);
    if (editingIndex === null) saved.push(s);
    else saved[editingIndex] = s;
    editingIndex = null;
    $('#save').textContent = '＋ Salvar cenário';
    persist();
    $('#comparison-result').replaceChildren();
    toast('Cenário salvo neste navegador.');
  } catch (error) {
    toast(error.message);
  }
});
function renderSaved() {
  renderEmploymentChoices();
  for (const id of ['#retro-before', '#retro-after']) {
    const select = $(id),
      old = select.value;
    select.replaceChildren(...saved.map((scenario, i) => new Option(scenario.name, String(i))));
    if (
      old !== '' &&
      saved[Number(old)] &&
      (id !== '#retro-after' || old !== $('#retro-before').value)
    )
      select.value = old;
    else if (id === '#retro-after' && saved.length > 1) select.value = String(saved.length - 1);
  }
  updateSecondaryControls();
  updateActions();
  $('#saved-count').textContent = saved.length;
  $('#saved-list').innerHTML = saved.length
    ? saved
        .map(
          (s, i) =>
            `<article class="panel saved-card"><span class="pill">SIMULAÇÃO SALARIAL</span><h3>${escape(s.name)}</h3><p>${escape(s.competence)} · Nível ${escape(s.level)}, grau ${escape(s.grade)}<br>${!s.gdpi_eligible ? 'GDPI não considerada' : s.gdpi_evaluation === 'no_institutional' ? `ADI/AED ${escape(s.adi)}% · sem AI` : s.gdpi_evaluation === 'statutory_70' ? 'Hipótese legal · notas de 70%' : `ADI ${escape(s.adi)}% · AI ${escape(s.ai)}%`}</p><div class="actions"><button class="secondary load-scenario" data-index="${i}">Editar</button><button class="secondary duplicate-scenario" data-index="${i}" ${saved.length >= 3 ? 'disabled' : ''}>Duplicar</button><button class="text-button delete-scenario" data-index="${i}">Excluir</button></div></article>`,
        )
        .join('') +
      (saved.length < 3
        ? `<article class="saved-card add-card"><h3>${saved.length === 1 ? 'Falta um para comparar' : 'Mais uma possibilidade'}</h3><p>Altere a Calculadora e clique em “Salvar cenário”. Cabem até três.</p><div class="actions"><button class="secondary" data-goto="calculator">Ir para a Calculadora</button></div></article>`
        : '')
    : `<div class="panel empty-state"><h3>Nenhum cenário salvo ainda</h3><ol><li>Monte uma simulação na Calculadora.</li><li>Clique em “Salvar cenário”. Cabem até três.</li><li>Volte aqui para comparar líquidos mensais e anuais.</li></ol><div class="actions"><button class="primary" id="save-current" ${$('#save').disabled ? 'disabled' : ''}>＋ Salvar o cenário atual</button><button class="secondary" data-goto="calculator">Ir para a Calculadora</button></div></div>`;
  $('#save-current')?.addEventListener('click', () => $('#save').click());
  $$('.delete-scenario').forEach((b) =>
    b.addEventListener('click', () => {
      saved.splice(Number(b.dataset.index), 1);
      editingIndex = null;
      $('#save').textContent = '＋ Salvar cenário';
      persist();
      $('#comparison-result').replaceChildren();
    }),
  );
  $$('.duplicate-scenario').forEach((b) =>
    b.addEventListener('click', () => {
      if (saved.length >= 3) return toast('O comparador admite até três cenários.');
      saved.push({
        ...structuredClone(saved[Number(b.dataset.index)]),
        name: (saved[Number(b.dataset.index)].name + ' · cópia').slice(0, 80),
      });
      persist();
    }),
  );
  $$('.load-scenario').forEach((b) =>
    b.addEventListener('click', () => {
      editingIndex = Number(b.dataset.index);
      $('#save').textContent = 'Salvar alterações';
      loadScenario(saved[editingIndex]);
    }),
  );
  updateActions();
}
async function loadScenario(s) {
  clearTimeout(timer);
  // Arquivos anteriores aos adicionais pessoais não podem herdar o vínculo aberto.
  for (const [key, value] of Object.entries({
    quinquennia: 0,
    ade_percent: '0',
    ade_calculation: 'entry_year',
    ade_entry_year: '',
    ade_evaluations: '',
    ade_adi: '',
    cost_allowance_days: '',
    cost_allowance_goals: '',
    cost_allowance_monthly: '',
    cost_allowance_daily: '',
  }))
    field(key).value = value;
  if (!s.ade_calculation && Number(s.ade_percent))
    field('ade_calculation').value = 'granted_percentage';
  for (const [key, value] of Object.entries(s)) {
    const input = field(key);
    if (!input || ['level', 'grade', 'commission', 'function'].includes(key)) continue;
    if (input.type === 'checkbox') input.checked = Boolean(value);
    else input.value = key === 'fraction' ? Number(value) * 100 : value;
  }
  if (!s.health_enrolled) field('age').value = '';
  field('complementary_percent').value = Number(s.complementary_rate || 0) * 100;
  $('#beneficiaries').replaceChildren();
  if (s.beneficiaries?.length) s.beneficiaries.forEach(beneficiaryRow);
  else beneficiaryRow();
  $('#rubrics').replaceChildren();
  (s.rubrics || []).forEach(rubricRow);
  updateEvaluationFields(true);
  showTab('calculator');
  await loadParameters();
  if (params) {
    field('level').value = s.level;
    updateGrades('#level', '#grade');
    field('grade').value = s.grade;
    field('commission').value = s.commission || '';
    field('function').value = s.function || '';
    field('remuneration_option').value = s.remuneration_option || 'none';
    field('commission_pension').checked = Boolean(s.commission_pension);
    field('function_pension').checked = Boolean(s.function_pension);
    updateControls();
    await calculate();
  }
}
function comparisonMarkup(r) {
  const metrics = [
    ['Bruto mensal', (x) => currency(x.monthly.gross)],
    ['Diferença bruta vs. primeiro', (x) => currency(x.difference.gross)],
    ['RPPS', (x) => currency(x.monthly.pension?.amount)],
    ['IPSEMG', (x) => currency(x.monthly.health?.amount)],
    ['IRRF', (x) => currency(x.monthly.income_tax?.amount)],
    ['Líquido mensal', (x) => currency(x.monthly.net)],
    ['Líquido anual estimado', (x) => currency(x.annual?.net)],
    ['Diferença mensal vs. primeiro', (x) => currency(x.difference.monthly)],
    [
      'Variação mensal',
      (x) =>
        x.difference.monthly_percent == null ? '—' : number(x.difference.monthly_percent) + '%',
    ],
    ['Diferença anual vs. primeiro', (x) => currency(x.difference.annual)],
    [
      'Variação anual',
      (x) =>
        x.difference.annual_percent == null ? '—' : number(x.difference.annual_percent) + '%',
    ],
  ];
  return `<div class="panel comparison-table"><div class="table-scroll"><table><thead><tr><th>INDICADOR</th>${r.results.map((x, i) => `<th>${escape(x.scenario.name)}${r.best_monthly === null && i === r.best_gross ? '<br><span>Maior bruto · líquido não apurado</span>' : ''}${i === r.best_monthly ? '<br><span class="best">↑ Maior líquido mensal</span>' : ''}${i === r.best_annual ? '<br><span class="best">↑ Maior líquido anual</span>' : ''}</th>`).join('')}</tr></thead><tbody>${metrics.map(([label, get]) => `<tr><td>${label}</td>${r.results.map((x) => `<td>${get(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="field-help">Mesma competência; projeção anual com remuneração constante. Empates indicam a primeira opção. ${r.results.some((x) => x.parameters.status === 'demo') ? 'Resultados com dados fictícios.' : ''}</p></div>`;
}
$('#run-compare').addEventListener('click', async () => {
  try {
    $('#comparison-result').innerHTML = comparisonMarkup(
      await api('/api/compare', { scenarios: saved }),
    );
  } catch (error) {
    $('#comparison-result').innerHTML =
      `<div class="error" role="alert">${escape(error.message)}</div>`;
  }
});
$('#compare-options').addEventListener('click', async () => {
  try {
    const result = await api('/api/commission-options', scenario());
    showTab('compare');
    $('#comparison-result').innerHTML = comparisonMarkup(result);
  } catch (error) {
    toast(error.message);
  }
});
$('#import-scenario').addEventListener('click', () => $('#import-file').click());
$('#import-file').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 1024 * 1024) throw new Error('Arquivo excede 1 MB.');
    let data;
    try {
      data = JSON.parse(await file.text());
    } catch {
      throw new Error(
        'Não foi possível ler este arquivo. Escolha uma simulação guardada pelo Horizonte.',
      );
    }
    const s = data.scenario || data;
    if (!['real', 'official'].includes(s.mode))
      throw new Error('Este arquivo não utiliza a tabela da carreira. Crie uma nova simulação.');
    if (saved.length >= 3) throw new Error('Exclua um cenário antes de importar.');
    const valid = await api('/api/calculate', s);
    saved.push(valid.scenario);
    persist();
    toast('Cenário validado e importado.');
  } catch (error) {
    toast(error.message);
  }
  event.target.value = '';
});
$('#reset').addEventListener('click', () => {
  clearTimeout(timer);
  editingIndex = null;
  $('#save').textContent = '＋ Salvar cenário';
  form.reset();
  field('commission').value = '';
  field('function').value = '';
  field('mode').value = 'real';
  $('#beneficiaries').replaceChildren();
  beneficiaryRow();
  $('#rubrics').replaceChildren();
  updateEvaluationFields(true);
  loadParameters();
});
$('#project-career').addEventListener('click', async () => {
  try {
    const r = await api('/api/career', {
      scenario: scenario(),
      future_level: $('#future-level').value,
      future_grade: $('#future-grade').value,
      years: Number($('#future-years').value),
    });
    const max = Math.max(1, ...r.series.map((x) => Math.abs(Number(x.accumulated_difference))));
    $('#career-result').innerHTML =
      `<div class="panel"><h2>Sua perspectiva de evolução</h2>${metric('Diferença bruta mensal', currency(r.gross_monthly_difference))}${metric('Diferença bruta anual', currency(r.gross_annual_difference))}${metric('Diferença líquida mensal', currency(r.monthly_difference))}${metric('Diferença anual estática', currency(r.annual_difference))}${
        r.series.every((x) => x.accumulated_difference != null)
          ? `<svg class="chart" viewBox="0 0 720 220" role="img" aria-label="Diferença líquida acumulada por ano">${r.series
              .map((x, i) => {
                const w = 650 / r.series.length,
                  h = (Math.abs(Number(x.accumulated_difference)) / max) * 135;
                return `<rect class="chart-bar ${i === r.series.length - 1 ? 'accent' : ''}" x="${40 + i * w}" y="${170 - h}" width="${w * 0.65}" height="${h}" rx="4"/><text x="${40 + i * w}" y="195">${x.year}a</text>`;
              })
              .join('')}</svg>`
          : ''
      }<div class="table-scroll"><table><thead><tr><th>ANO</th><th>DIFERENÇA ACUMULADA · ${r.monthly_difference === null ? 'BRUTA' : 'LÍQUIDA'}</th></tr></thead><tbody>${r.series.map((x) => `<tr><td>${x.year}</td><td>${currency(x.accumulated_difference ?? x.accumulated_gross_difference)}</td></tr>`).join('')}</tbody></table></div><p class="field-help">${escape(r.assumptions)} Barras mostram a magnitude; a tabela preserva o sinal das diferenças.</p></div>`;
  } catch (error) {
    $('#career-result').innerHTML =
      `<div class="error" role="alert">${escape(error.message)}</div>`;
  }
});
// Na primeira visita à aba, já projeta a próxima posição da tabela em vez de abrir vazia.
document.addEventListener('tab:shown', (event) => {
  if (event.detail !== 'career' || !params || !$('.career-placeholder')) return;
  const positions = params.positions.map((p) => `${p.level}-${p.grade}`);
  const next = positions[positions.indexOf(`${field('level').value}-${field('grade').value}`) + 1];
  if (!next) return;
  const [level, grade] = next.split('-');
  $('#future-level').value = level;
  updateGrades('#future-level', '#future-grade');
  $('#future-grade').value = grade;
  updateActions();
  if (!$('#project-career').disabled) $('#project-career').click();
});
$('#calculate-retro').addEventListener('click', async () => {
  try {
    const before = saved[Number($('#retro-before').value)],
      after = saved[Number($('#retro-after').value)];
    if (!before || !after || $('#retro-before').value === $('#retro-after').value)
      throw new Error('Selecione duas situações salvas diferentes.');
    const start = $('#retro-start').value,
      end = $('#retro-end').value;
    if (!start || !end || start > end) throw new Error('Confira o início e o fim do período.');
    const entries = [];
    let [year, month] = start.split('-').map(Number);
    while (`${year}-${String(month).padStart(2, '0')}` <= end) {
      if (entries.length >= 60) throw new Error('Selecione um período de até 60 meses.');
      const competence = `${year}-${String(month).padStart(2, '0')}`;
      entries.push([
        { ...before, competence },
        { ...after, competence },
      ]);
      month++;
      if (month > 12) {
        month = 1;
        year++;
      }
    }
    const r = await api('/api/retroactive', { entries });
    $('#retro-result').innerHTML =
      `<div class="callout">${r.entries.map((e) => metric(e.competence, currency(e.net_difference ?? e.gross_difference))).join('')}${metric('Total das diferenças brutas', currency(r.total_gross_difference))}${metric('Total das diferenças líquidas', currency(r.total_net_difference))}<p>Diferenças estimadas por competência, sem juros ou correção monetária. O imposto sobre o pagamento acumulado pode ser diferente, conforme a forma e a data do recebimento.</p></div>`;
  } catch (error) {
    $('#retro-result').innerHTML = `<div class="error" role="alert">${escape(error.message)}</div>`;
  }
});

const dateLabel = (value) =>
  value ? new Date(value + 'T12:00:00').toLocaleDateString('pt-BR') : '—';
function calculationNotes(r) {
  const notes = [
    'Estimativa para servidor ativo. Confira sua posição, avaliações, opções previdenciárias e demais parcelas com o contracheque.',
    'As faixas previdenciárias são atualizadas pelos reajustes anuais previstos na LC nº 64/2002. Diferenças de enquadramento ou arredondamento podem alterar o valor descontado.',
    'O imposto apresentado é a retenção estimada da folha. O valor definitivo depende da declaração anual.',
  ];
  if (r.annual)
    notes.push(
      'O total anual considera remuneração constante, 13º integral e uma folha de férias com terço, sem reajustes futuros.',
    );
  if (Number(r.scenario.alimony))
    notes.push(
      'Os reflexos da pensão alimentícia em férias e 13º dependem da decisão judicial ou do acordo aplicável.',
    );
  if (r.scenario.health_enrolled)
    notes.push(
      'A inclusão de familiares e as isenções do IPSEMG dependem do reconhecimento dos requisitos pelo Instituto.',
    );
  const ade = r.monthly.earnings.find((e) => e.name === 'ADE')?.calculation;
  const adiOrigin =
    ade?.individual_origin === 'ade'
      ? 'A ADI é a informada para o ADE'
      : 'Sem ADI própria do ADE, foi usada a ADI da GDPI';
  if (ade?.factor != null && ade.institutional == null)
    notes.push(
      `O ADE é a faixa máxima × ADI. Sem avaliação institucional, a ADI é considerada integralmente (Decreto nº 46.756/2015). ${adiOrigin}; abaixo de 70, não há ADE no exercício. Por ano de ingresso, a quantidade de avaliações é o ano da competência menos o de ingresso.`,
    );
  else if (ade?.factor != null)
    notes.push(
      `O ADE segue o índice da Seplag: faixa máxima × (0,3 × AI + 0,7 × ADI). A AI é ${number(ade.institutional)}, nota atribuída a órgão sem Acordo de Resultados. ${ade.individual_origin === 'ade' ? 'A ADI é a informada para o ADE' : 'Sem ADI própria do ADE, foi usada a ADI da GDPI'}; abaixo de 70, não há ADE no exercício. Por ano de ingresso, a quantidade de avaliações é o ano da competência menos o de ingresso.`,
    );
  else if (['entry_year', 'evaluations'].includes(r.scenario.ade_calculation))
    notes.push(
      'O ADE é estimado com avaliações satisfatórias e aproveitamento integral da faixa. Por ano de ingresso, a quantidade corresponde ao ano da competência menos o ano de ingresso.',
    );
  if (r.parameters.status === 'demo')
    notes.unshift(
      'Este arquivo contém valores de exemplo. Faça uma nova simulação com a tabela da carreira antes de planejar sua remuneração.',
    );
  return notes;
}
function earningReference(e) {
  if (e.calculation) {
    const c = e.calculation;
    return `${e.name === 'Quinquênio' ? 'CE/MG · ADCT, art. 112' : 'Lei nº 14.693/2003 · Decreto nº 44.503/2007'} · ${currency(c.base)} × ${number(Number(c.rate) * 100)}% × ${number(c.fraction)}${c.base_origin === 'recognized_base' ? ' · base reconhecida informada' : ''}${c.factor == null ? '' : c.institutional == null ? ` · faixa ${number(Number(c.ceiling) * 100)}% × ADI ${number(c.individual)}%` : ` · faixa ${number(Number(c.ceiling) * 100)}% × (0,3 × AI ${number(c.institutional)} + 0,7 × ADI ${number(c.individual)})`}${c.evaluations != null ? ' · ' + number(c.evaluations) + ' avaliações satisfatórias' : ''}${c.entry_year != null ? ' · ingresso em ' + c.entry_year : ''}`;
  }
  if (e.name === 'Vencimento básico') return 'Lei nº 25.804/2026 · tabela de vencimentos SEPLAG';
  if (e.name === 'GDPI') return 'Lei nº 13.085/1998 · Decreto nº 46.030/2012';
  if (/^(DAD|FGD|GTED)-/.test(e.name)) return 'Lei Delegada nº 174/2007 · tabela SEPLAG';
  if (/^(DAI|FGI|GTEI)-/.test(e.name)) return 'Lei Delegada nº 175/2007 · tabela SEPLAG';
  return e.source || 'Valor informado na simulação';
}
function publicSourceLink(item) {
  const u = new URL(item.url);
  if (u.protocol !== 'https:') return escape(item.title);
  return `<a href="${escape(item.url)}" target="_blank" rel="noopener noreferrer">${escape(item.title)} <span aria-hidden="true">↗</span></a>`;
}
const searchText = (value) =>
  value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\.(?=\d)/g, '')
    .toLowerCase();
async function loadSources() {
  const target = $('#sources-content');
  try {
    const { catalog } = await api('/api/sources');
    target.innerHTML = `<div class="panel source-intro"><h2>${escape(catalog.title)}</h2><p>${escape(catalog.description)}</p><label>Buscar norma ou assunto<input id="source-search" type="search" placeholder="Ex.: GDPI, IPSEMG, férias, 18.974" autocomplete="off"></label><p class="field-help">As alterações de uma norma devem ser lidas em conjunto com o texto consolidado. Regras de aposentadoria e concessão de direitos exigem análise do vínculo.</p></div><div id="source-groups" class="sources-grid"></div><div class="panel"><h2>Como interpretar a estimativa</h2><p>Os valores consideram os dados informados para a competência escolhida. A projeção anual mantém a remuneração constante e pressupõe direito integral a férias e 13º.</p><p>O enquadramento previdenciário, as avaliações de desempenho, os dependentes e as opções contributivas devem corresponder à situação funcional do servidor. A simulação não concede direitos nem substitui o contracheque.</p><p>Suas simulações são guardadas neste navegador. Você pode salvá-las em arquivo e recuperá-las depois.</p></div>`;
    const render = () => {
      const query = searchText($('#source-search').value.trim());
      const groups = catalog.sections
        .map((section) => ({
          ...section,
          items: section.items.filter((item) =>
            searchText(section.title + ' ' + item.title + ' ' + item.description).includes(query),
          ),
        }))
        .filter((section) => section.items.length);
      $('#source-groups').innerHTML = groups.length
        ? groups
            .map(
              (section) =>
                `<section class="panel source-section"><h2>${escape(section.title)}</h2><ul class="document-list">${section.items.map((item) => `<li>${publicSourceLink(item)}<p>${escape(item.description)}</p></li>`).join('')}</ul></section>`,
            )
            .join('')
        : '<p role="status">Nenhuma referência encontrada. Tente o número da norma ou outro assunto.</p>';
    };
    $('#source-search').addEventListener('input', render);
    render();
    await loadRealCatalog();
  } catch (error) {
    target.innerHTML = `<div class="error">${escape(error.message)}</div>`;
  }
}

let lastEmployment = null;
function renderEmploymentChoices() {
  $('#employment-result').replaceChildren();
  lastEmployment = null;
  $('#employment-choices').innerHTML =
    saved.length < 1
      ? '<p>Salve pelo menos um cenário EPPGG de referência.</p>'
      : saved
          .map(
            (s, i) =>
              `<div class="mini-panel employment-choice" data-index="${i}"><label class="check"><input type="checkbox" class="include-employment" checked> ${escape(s.name)} · ${escape(s.competence)}</label><label>Fonte pagadora<input class="payer" value="Estado de Minas Gerais" maxlength="100" required></label></div>`,
          )
          .join('');
}
function specialWarnings(r) {
  const notes = [
    'A acumulação dos vínculos deve ser legalmente permitida. Uma comissão integra o vínculo efetivo e não corresponde a outro emprego.',
    'A contribuição previdenciária é apurada por cargo. A assistência IPSEMG incide uma vez sobre a maior remuneração estadual.',
    'O IR é calculado por fonte pagadora. Use o mesmo nome para a mesma fonte e informe cada desconto apenas onde ele é efetivamente cobrado.',
    r.annual
      ? 'O anual mantém a remuneração constante e inclui férias com terço e 13º integrais.'
      : 'A estimativa é mensal. As férias e o 13º de fontes informadas por contracheque dependem de seus próprios valores.',
    'A retenção mensal não representa o imposto definitivo da declaração anual.',
  ];
  return `<ul class="warning-list">${notes.map((w) => `<li>${escape(w)}</li>`).join('')}</ul>`;
}
function memoryButton(id) {
  return `<button class="secondary" id="${id}">↓ Baixar memória de cálculo</button>`;
}
$('#consolidate-employments').addEventListener('click', async () => {
  const target = $('#employment-result');
  try {
    const employments = $$('.employment-choice')
      .filter((row) => $('.include-employment', row).checked)
      .map((row) => ({
        payer: $('.payer', row).value,
        scenario: saved[Number(row.dataset.index)],
      }));
    if ($('#include-reported').checked) {
      const reported = Object.fromEntries(
        $$('[data-reported]').map((input) => [input.dataset.reported, input.value]),
      );
      if ($('#reported-ipsemg-base').value) reported.ipsemg_base = $('#reported-ipsemg-base').value;
      employments.push({ payer: $('#reported-payer').value, reported });
    }
    lastEmployment = await api('/api/multiple-employments', {
      employments,
      lawful_accumulation_confirmed: $('#lawful-accumulation').checked,
    });
    const r = lastEmployment,
      m = r.monthly;
    target.innerHTML = `<h3>Líquido conjunto dos vínculos</h3>${metric('Bruto conjunto', currency(m.gross))}${m.employments.map((e) => metric(e.name + ' · RPPS', currency(e.pension.amount))).join('')}${metric('IPSEMG único · maior base ' + currency(m.health.base), currency(m.health.amount))}${m.income_tax_sources.map((t) => metric('IRRF · ' + t.payer, currency(t.income_tax.amount))).join('')}${metric('Descontos totais', currency(m.deductions))}${metric('Líquido mensal conjunto', currency(m.net))}${r.annual ? metric('Líquido anual estimado conjunto', currency(r.annual.net)) : ''}${specialWarnings(r)}${memoryButton('export-employments')}`;
    $('#export-employments').addEventListener('click', () =>
      download(
        new Blob([JSON.stringify(lastEmployment, null, 2)], { type: 'application/json' }),
        'eppgg-vinculos.json',
      ),
    );
  } catch (e) {
    lastEmployment = null;
    target.innerHTML = `<div class="error" role="alert">${escape(e.message)}</div>`;
  }
});
function updateEvaluationFields(reset = false) {
  const mode = field('gdpi_evaluation').value;
  // Só troca os valores quando o enquadramento muda: reescrever a cada tecla apagava
  // a vírgula ou o ponto ainda sem casas decimais (ex.: "95,").
  const changed = reset || mode !== previousEvaluation;
  if (reset) {
    manualGrades = {
      adi: field('adi').value || '95',
      ai: mode === 'normal' ? field('ai').value : '',
    };
  } else if (changed && previousEvaluation !== 'statutory_70') {
    manualGrades.adi = field('adi').value;
    if (previousEvaluation === 'normal') manualGrades.ai = field('ai').value;
  }
  const automatic = mode === 'statutory_70',
    eligible = field('gdpi_eligible').checked;
  if (changed) {
    field('adi').value = automatic ? '70' : manualGrades.adi;
    field('ai').value = automatic ? '70' : mode === 'normal' ? manualGrades.ai : '';
  }
  field('adi').disabled = !eligible || automatic;
  field('ai').disabled = !eligible || mode !== 'normal';
  field('adi').required = eligible && !automatic;
  field('ai').required = eligible && mode === 'normal';
  field('gdpi_evaluation').disabled = !eligible;
  field('ai').placeholder = mode === 'no_institutional' ? 'Sem nota' : 'Informe a nota';
  $('#ai-label').textContent =
    mode === 'normal' && eligible ? 'Institucional · AI (%)' : 'Institucional · inativo';
  previousEvaluation = mode;
}
function updateBeneficiaryControls(div) {
  const relationship = $('.relationship', div).value;
  const allowed = compatibleBeneficiaryRelationships(div);
  $$('.relationship option', div).forEach((option) => {
    const incompatible = option.value && !allowed.includes(option.value);
    // Keep imported invalid selections visible for the server's validation.
    option.hidden = Boolean(incompatible && option.value !== relationship);
    option.disabled = Boolean(incompatible);
  });
  const special = $('.special-condition', div),
    age = $('.beneficiary-age', div);
  const enrolled = field('age').value !== '';
  age.disabled = !relationship || !enrolled;
  age.required = Boolean(relationship) && enrolled;
  special.closest('label').hidden = relationship !== 'child';
  special.disabled = relationship !== 'child' || !enrolled;
  if (special.disabled) special.checked = false;
}
function updateRubricControls(div) {
  const deduction = $('.rubric-nature', div).value === 'deduction';
  $$('[data-flag]', div).forEach((input) => {
    const incidence = input.dataset.flag !== 'proportional';
    input.disabled =
      (deduction && incidence) ||
      (!field('project_annual').checked && ['vacation', 'thirteenth'].includes(input.dataset.flag));
    if (deduction && incidence) input.checked = false;
  });
}
function updateSecondaryControls() {
  const available = saved.length > 0,
    reported = available && $('#include-reported').checked;
  $('#include-reported').disabled = !available;
  for (const input of [
    $('#reported-payer'),
    ...$$('[data-reported]'),
    $('#reported-ipsemg-base'),
  ]) {
    input.disabled = !reported;
    input.required = reported && input.id !== 'reported-ipsemg-base';
  }
  const rows = $$('.employment-choice').filter((row) => $('.include-employment', row).checked);
  const enough = rows.length + (reported ? 1 : 0) >= 2 && rows.length > 0;
  $('#lawful-accumulation').disabled = !enough;
  const validReported =
    !reported ||
    [$('#reported-payer'), ...$$('[data-reported]'), $('#reported-ipsemg-base')].every(
      (input) => input.checkValidity() && (input.type === 'number' || input.value.trim()),
    );
  $('#consolidate-employments').disabled =
    !enough ||
    !$('#lawful-accumulation').checked ||
    !validReported ||
    rows.some((row) => !$('.payer', row).value.trim());
  for (const id of ['#retro-before', '#retro-after', '#retro-start', '#retro-end'])
    $(id).disabled = saved.length < 2;
  const start = $('#retro-start').value,
    end = $('#retro-end').value;
  $('#calculate-retro').disabled =
    saved.length < 2 ||
    $('#retro-before').value === $('#retro-after').value ||
    !start ||
    !end ||
    start > end;
}
function updateActions() {
  for (const id of ['#level', '#grade', '#future-level', '#future-grade', '#future-years'])
    $(id).disabled = !params;
  const usable = Boolean(params) && form.checkValidity();
  $('#save').disabled =
    !usable || !lastResult || calculationBusy || (saved.length >= 3 && editingIndex === null);
  $('#compare-options').disabled =
    !usable || !lastResult || calculationBusy || !field('commission').value;
  $$('#result .export').forEach((button) => (button.disabled = !lastResult || calculationBusy));
  $('#project-career').disabled =
    !usable ||
    !lastResult ||
    calculationBusy ||
    !$('#future-level').value ||
    !$('#future-grade').value ||
    !$('#future-years').value ||
    !$('#future-years').checkValidity();
  $('#run-compare').disabled =
    saved.length < 2 || saved.some((s) => s.competence !== saved[0].competence);
  $('#import-scenario').disabled = saved.length >= 3;
}
function updateCostAllowance() {
  const alternatives = ['cost_allowance_goals', 'cost_allowance_monthly', 'cost_allowance_daily'];
  const active = alternatives.find((name) => field(name).value !== '');
  for (const name of alternatives) field(name).disabled = Boolean(active && name !== active);
  field('cost_allowance_days').disabled = active === 'cost_allowance_monthly';
  field('cost_allowance_days').required = active === 'cost_allowance_daily' ||
    (active === 'cost_allowance_goals' && decimal(field(active).value) !== '100');
}
function updateControls() {
  updateCostAllowance();
  updateEvaluationFields();
  updateCommissionChoices();
  updatePersonalAdditions();
  if (!params) {
    field('commission_pension').disabled = true;
    field('function_pension').disabled = true;
    $('#compare-options').disabled = true;
  }
  const capped = field('capped_pension').checked;
  field('complementary_percent').disabled = !capped;
  field('complementary_deductible').disabled =
    !capped || Number(field('complementary_percent').value) <= 0;
  if (field('complementary_deductible').disabled) field('complementary_deductible').checked = false;
  field('copay').disabled = field('age').value === '';
  $('#add-beneficiary').hidden = $$('.beneficiary').length >= 30 || !compatibleBeneficiaryRelationships().length;
  $('#add-beneficiary').disabled = $$('.beneficiary').some((div) => !$('.relationship', div).value);
  $$('.beneficiary').forEach(updateBeneficiaryControls);
  $$('.rubric').forEach(updateRubricControls);
  $('#add-rubric').disabled = $$('.rubric').length >= 50;
  validateDecimals();
  updateSecondaryControls();
  updateActions();
}
function updatePersonalAdditions() {
  field('quinquennia').disabled = false;
  field('ade_calculation').disabled = false;
  if (
    field('ade_calculation').value === 'granted_percentage' &&
    !Number(field('ade_percent').value)
  )
    field('ade_calculation').value = 'entry_year';
  const method = field('ade_calculation').value;
  field('ade_adi').disabled = method === 'granted_percentage';
  field('ade_entry_year').disabled = method !== 'entry_year';
  field('ade_evaluations').disabled = method !== 'evaluations';
  field('ade_entry_year').required = false;
  field('ade_evaluations').required = false;
  field('ade_entry_year').max = field('competence').value.slice(0, 4);
  $('#ade-year-field').hidden = method !== 'entry_year';
  $('#ade-count-field').hidden = method !== 'evaluations';
}
$('#compare').addEventListener('input', updateSecondaryControls);
$('#compare').addEventListener('change', updateSecondaryControls);
for (const id of [
  '#future-grade',
  '#future-years',
  '#retro-before',
  '#retro-after',
  '#retro-start',
  '#retro-end',
]) {
  $(id).addEventListener('input', () => {
    updateSecondaryControls();
    updateActions();
  });
  $(id).addEventListener('change', () => {
    updateSecondaryControls();
    updateActions();
  });
}

renderSaved();
loadParameters();
{
  const initialTab = location.hash.slice(1);
  if ($(`.tab[data-tab="${CSS.escape(initialTab)}"]`)) showTab(initialTab);
}

function updateCommissionChoices() {
  if (!params) return;
  let cargo = params.commissions.find((item) => item.code === field('commission').value);
  if (field('remuneration_option').value === 'none') cargo = null;
  if (!cargo) {
    field('commission').value = '';
    field('remuneration_option').value = 'none';
  }
  const fn = (params.functions || []).find((item) => item.code === field('function').value);
  const compatible =
    fn && (fn.requires_commission_kind ? cargo?.kind === fn.requires_commission_kind : !cargo);
  if (!compatible) {
    field('function').value = '';
    field('function_pension').checked = false;
  }
  for (const family of ['DAD', 'GTED', 'DAI', 'GTEI', 'FGD', 'FGI']) {
    const select = $('#' + family.toLowerCase());
    select.value = ['DAD', 'DAI'].includes(family)
      ? cargo?.kind === family
        ? cargo.code
        : ''
      : compatible && fn.kind === family
        ? fn.code
        : '';
    select.disabled = ['FGD', 'FGI'].includes(family)
      ? Boolean(cargo)
      : family === 'GTED'
        ? cargo?.kind !== 'DAD'
        : family === 'GTEI'
          ? cargo?.kind !== 'DAI'
          : false;
  }
  for (const option of field('remuneration_option').options) {
    option.disabled = option.value !== 'none' && (!cargo || !cargo['allow_' + option.value]);
  }
  field('remuneration_option').disabled = !cargo;
  field('function_pension').disabled = !compatible || !fn.optional_pension;
  if (field('function_pension').disabled) field('function_pension').checked = false;
  field('commission_pension').disabled = !cargo || !cargo.optional_pension;
  if (field('commission_pension').disabled) field('commission_pension').checked = false;
  $('#compare-options').disabled = !cargo;
}

function renderRealResult(r) {
  const m = r.monthly,
    g = r.gdpi,
    a = r.annual;
  $('#result').innerHTML =
    `<div class="summary-grid"><div class="stat"><span class="stat-label">Remuneração bruta real</span><span class="stat-value">${currency(m.gross)}</span><span class="stat-sub">Valores publicados pela SEPLAG</span></div><div class="stat"><span class="stat-label">GDPI calculada</span><span class="stat-value">${currency(g.actual)}</span><span class="stat-sub">50% dos pontos · avaliações aplicadas</span></div><div class="stat net"><span class="stat-label">Líquido mensal</span><span class="stat-value">A conferir</span><span class="stat-sub">Descontos reais ainda não apurados</span></div></div>
<div class="panel"><div class="result-title"><div><h2>Remuneração com dados reais</h2><p>${escape(r.scenario.name)} · ${escape(r.scenario.competence)} · Nível ${escape(r.scenario.level)}, grau ${escape(r.scenario.grade)}</p></div><span class="pill verified">FONTES OFICIAIS</span></div><div class="table-scroll"><table><thead><tr><th>PROVENTO / FONTE</th><th>VALOR BRUTO</th></tr></thead><tbody>${m.earnings.map((row) => `<tr><td><span class="rubric-name">${escape(row.name)}</span><span class="source-small">${escape(row.source)}</span></td><td class="amount">${currency(row.amount)}</td></tr>`).join('')}<tr class="total-row"><td>Total bruto estimado</td><td>${currency(m.gross)}</td></tr></tbody></table></div><div class="callout">O bruto usa vencimentos, pontos GDPI e valores de cargos/funções reais. RPPS, IPSEMG, IRRF e demais descontos não foram aplicados neste modo. O total acima não é o valor líquido a receber.</div><div class="export-bar"><span>Vigência da remuneração: ${dateLabel(r.parameters.valid_from)} a ${dateLabel(r.parameters.valid_until)}</span><div class="actions"><button class="secondary export" data-format="csv">↓ Baixar planilha</button><button class="secondary export" data-format="json">↓ Guardar simulação</button></div></div></div>
<div class="subgrid"><div class="panel"><h2>GDPI · regra legal aplicada</h2>${metric('Pontuação máxima do Anexo V', number(g.points))}${metric('Quota variável da pontuação', number(Number(g.point_share) * 100) + '%')}${metric('Pontos utilizados na fórmula', number(g.effective_points))}${metric('Fator legal', g.factor)}${metric('VB referência · nível V, grau J', currency(g.reference_salary))}${metric('Resultado da avaliação', number(Number(g.evaluation) * 100) + '%')}${metric('Teto com notas de 100%', currency(g.ceiling))}${metric('GDPI efetiva', currency(g.actual))}<p class="field-help">Pontos variáveis × fator legal × vencimento de referência × avaliação × proporção do mês.</p>${!g.eligible ? '<div class="callout">GDPI zerada: nota mínima individual ou elegibilidade não atendida.</div>' : ''}</div><div class="panel"><h2>Projeções brutas</h2>${a ? `${metric('13º bruto integral', currency(a.thirteenth.gross))}${metric('Folha de férias + terço · bruto', currency(a.vacation.gross))}${metric('Anual bruto estático', currency(a.gross))}<p class="field-help">${escape(a.assumptions)}</p>` : '<p>Projeção anual desativada.</p>'}<div class="callout">A remuneração de cargo comissionado depende da opção do servidor. Confira os requisitos de percepção da GDPI e a compatibilidade das funções.</div></div></div>
<div class="panel breakdown"><h2>Fontes e limites da simulação</h2>${metric('Vigência disponibilizada', `${dateLabel(r.parameters.valid_from)} a ${dateLabel(r.parameters.valid_until)}`)}${metric('Conferência documental', r.parameters.verified_at)}<details><summary>Regras e ressalvas</summary><ul class="warning-list">${calculationNotes(
      r,
    )
      .map((w) => `<li>${escape(w)}</li>`)
      .join(
        '',
      )}</ul></details><details><summary>Descontos desta competência</summary><ul><li>Não há informações suficientes para estimar os descontos desta competência. O valor exibido corresponde à remuneração bruta.</li></ul></details></div>`;
  $$('.export').forEach((b) => b.addEventListener('click', () => exportResult(b.dataset.format)));
}

async function loadRealCatalog() {
  const data = await api('/api/career-data');
  const panel = document.createElement('div');
  panel.className = 'panel real-catalog';
  const families = ['DAD', 'GTED', 'DAI', 'GTEI', 'FGD', 'FGI'];
  panel.innerHTML = `<h2>Vencimentos, cargos e funções · 2026</h2><p>50 posições, 52 cargos e 45 funções/gratificações. Valores publicados pela SEPLAG para a competência de 2026.</p><details><summary>Vencimento básico e pontuação GDPI · todas as posições</summary><div class="table-scroll"><table><thead><tr><th>POSIÇÃO</th><th>VB</th><th>PONTOS TABELA</th><th>PONTOS VARIÁVEIS · 50%</th></tr></thead><tbody>${data.positions.map((p) => `<tr><td>${escape(p.level)}-${escape(p.grade)}</td><td>${currency(p.salary)}</td><td>${number(p.points)}</td><td>${number(Number(p.points) * Number(data.gdpi_point_share))}</td></tr>`).join('')}</tbody></table></div></details>${families
    .map((family) => {
      const rows = [...data.commissions, ...data.functions].filter((v) => v.kind === family);
      return `<details><summary>${family} · ${rows.length} níveis</summary><div class="table-scroll"><table><thead><tr><th>CARGO / FUNÇÃO</th><th>VALOR INTEGRAL</th></tr></thead><tbody>${rows.map((v) => `<tr><td>${escape(v.code)}</td><td>${currency(v.amount)}</td></tr>`).join('')}</tbody></table></div></details>`;
    })
    .join('')}`;
  $('#sources-content').append(panel);
}

if (!$$('.beneficiary').length) {
  beneficiaryRow();
  updateControls();
}
