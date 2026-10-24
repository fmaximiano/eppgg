'use strict';
// Cenários hipotéticos. Usa o cenário da Calculadora e as funções de app.js
// ($, $$, api, scenario, currency, escape, metric, download, showTab).
{
  const section = $('#hypotheses');
  const cards = $$('.hyp-card', section);
  const summary = $('#hyp-base-summary');
  const status = $('#hyp-status');
  const percent = (value) =>
    new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 4 }).format(Number(value));
  const monthLabel = (value) => value.split('-').reverse().join('/');
  let base = null; // último resultado válido da Calculadora
  let stale = true;
  let tableLoaded = false;

  for (const card of cards) {
    const levels = [
      'I',
      'II',
      'III',
      'IV',
      'V',
      ...(card.dataset.kind === 'level_vi' ? ['VI'] : []),
    ];
    $('.hyp-position', card).innerHTML = `<div class="field-row">
      <label>Nível simulado<select data-param="level"><option value="">Nível atual</option>${levels
        .map((level) => `<option>${level}</option>`)
        .join('')}</select></label>
      <label>Grau simulado<select data-param="grade"><option value="">Grau atual</option>${[
        ...'ABCDEFGHIJ',
      ]
        .map((grade) => `<option>${grade}</option>`)
        .join('')}</select></label>
    </div>`;
    card.addEventListener('input', () => schedule(card));
    card.addEventListener('change', () => schedule(card));
  }

  function cancel(card) {
    clearTimeout(card.timer);
    card.sequence = (card.sequence || 0) + 1;
  }

  function schedule(card, delay = 500) {
    cancel(card);
    if (!base) return;
    $('.hyp-result', card).innerHTML = '<p class="field-help">Atualizando…</p>';
    card.timer = setTimeout(() => run(card), delay);
  }

  async function run(card) {
    cancel(card);
    const sequence = card.sequence;
    const output = $('.hyp-result', card);
    const param = (name) => $(`[data-param="${name}"]`, card);
    try {
      for (const input of $$('[data-param]', card))
        if (!input.checkValidity()) throw new Error('Confira os valores deste cenário.');
      const body = {
        scenario: scenario(),
        kind: card.dataset.kind,
        level: param('level').value || null,
        grade: param('grade').value || null,
      };
      if (param('combine_gdpi')) body.combine_gdpi = param('combine_gdpi').checked;
      if (param('increase_percent')) body.increase_percent = param('increase_percent').value;
      if (param('months')) body.months = Number(param('months').value);
      output.innerHTML = `<p class="field-help">${
        body.kind === 'inflation' ? 'Consultando o IPCA e calculando…' : 'Calculando…'
      }</p>`;
      const result = await api('/api/hypotheses', body);
      if (sequence === card.sequence) render(card, result);
    } catch (error) {
      if (sequence !== card.sequence) return;
      output.innerHTML = `<div class="error" role="alert">${escape(error.message)}
        <button type="button" class="text-button hyp-retry">Tentar novamente</button></div>`;
      $('.hyp-retry', output).addEventListener('click', () => run(card));
    }
  }

  function render(card, result) {
    const { monthly, hypothesis } = result;
    const difference = Number(hypothesis.difference.monthly_net);
    const trend = difference > 0 ? 'up' : difference < 0 ? 'down' : '';
    const inflation = hypothesis.inflation;
    $('.hyp-result', card).innerHTML = `
      <div class="hyp-net">
        <span class="small-title">Líquido mensal · ${escape(result.scenario.level)}-${escape(result.scenario.grade)}</span>
        <span class="big-inline">${currency(monthly.net)}</span>
        <span class="hyp-difference ${trend}">${difference > 0 ? '+' : ''}${currency(difference)} por mês</span>
      </div>
      ${metric('Bruto mensal', currency(monthly.gross))}
      ${metric('Descontos', currency(monthly.deductions))}
      ${result.annual ? metric('Líquido anual estimado', currency(result.annual.net)) : ''}
      ${
        inflation
          ? `<p class="field-help">IPCA acumulado de ${percent(inflation.rate_percent)}%
            (${monthLabel(inflation.from)} a ${monthLabel(inflation.through)}) ·
            <a href="${escape(inflation.source_url)}" target="_blank" rel="noopener noreferrer">Banco Central</a></p>`
          : ''
      }
      <details>
        <summary>Composição do cálculo</summary>
        ${monthly.earnings.map((item) => metric(item.name, currency(item.amount))).join('')}
        ${metric('RPPS', currency(monthly.pension.amount))}
        ${metric('IPSEMG', currency(monthly.health.amount))}
        ${metric('IRRF', currency(monthly.income_tax.amount))}
      </details>
      <details>
        <summary>Hipóteses consideradas</summary>
        <p class="field-help">Comparado com ${escape(hypothesis.baseline.level)}-${escape(
          hypothesis.baseline.grade,
        )}, líquido de ${currency(hypothesis.baseline.monthly_net)}.</p>
        <ul class="hyp-assumptions">${hypothesis.assumptions
          .map((item) => `<li>${escape(item)}</li>`)
          .join('')}</ul>
      </details>
      <button type="button" class="secondary full hyp-download">↓ Baixar memória do cálculo</button>`;
    $('.hyp-download', card).addEventListener('click', () =>
      download(
        new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }),
        `cenario-hipotetico-${card.dataset.kind}.json`,
      ),
    );
  }

  async function loadTable() {
    if (tableLoaded) return;
    tableLoaded = true;
    try {
      const rows = await api('/api/hypotheses/level-vi');
      $('#hyp-level-vi').innerHTML = rows
        .map(
          (row) =>
            `<tr><td>${escape(row.grade)}</td><td>${currency(row.salary)}</td><td>${row.points}</td><td>${row.variable_points}</td></tr>`,
        )
        .join('');
    } catch {
      tableLoaded = false;
    }
  }

  function refresh() {
    if (!section.classList.contains('active')) {
      stale = true;
      return;
    }
    stale = false;
    loadTable();
    if (!base) {
      summary.textContent = 'Cenário incompleto';
      status.textContent = 'Complete os dados na Calculadora para simular as hipóteses.';
      for (const card of cards) {
        cancel(card);
        $('.hyp-result', card).replaceChildren();
      }
      return;
    }
    const s = base.scenario;
    summary.textContent = `${s.name} · ${monthLabel(s.competence)} · Nível ${s.level}, grau ${
      s.grade
    } · líquido de ${currency(base.monthly.net)}`;
    status.textContent = 'Os cenários são recalculados sempre que a Calculadora muda.';
    cards.forEach((card) => schedule(card, 0));
  }

  document.addEventListener('scenario:updated', (event) => {
    base = event.detail;
    refresh();
  });
  document.addEventListener('tab:shown', (event) => {
    if (event.detail === 'hypotheses' && stale) refresh();
  });
}
