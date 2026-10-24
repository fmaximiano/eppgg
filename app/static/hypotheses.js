(() => {
  'use strict';

  const $ = (selector, node = document) => node.querySelector(selector);
  const $$ = (selector, node = document) => [...node.querySelectorAll(selector)];

  const esc = (value) =>
    String(value ?? '').replace(
      /[&<>"']/g,
      (character) =>
        ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;',
        })[character],
    );

  const currency = (value) =>
    value == null
      ? '—'
      : new Intl.NumberFormat('pt-BR', {
          style: 'currency',
          currency: 'BRL',
        }).format(Number(value));

  const number = (value) =>
    new Intl.NumberFormat('pt-BR', {
      maximumFractionDigits: 4,
    }).format(Number(value));

  const monthLabel = (value) => {
    const [year, month] = value.split('-');
    return `${month}/${year}`;
  };

  function stylesheet(doc) {
    if (doc.getElementById('hypothesis-stylesheet')) return;
    const link = doc.createElement('link');
    link.id = 'hypothesis-stylesheet';
    link.rel = 'stylesheet';
    link.href = '/static/hypotheses.css';
    doc.head.appendChild(link);
  }

  function installTab() {
    const tabs = $('header .tabs');
    const main = $('#main');
    if (!tabs || !main || $('#hypotheses')) return;

    stylesheet(document);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tab';
    button.dataset.tab = 'hypotheses';
    button.textContent = 'Cenários hipotéticos';
    tabs.appendChild(button);

    const section = document.createElement('section');
    section.id = 'hypotheses';
    section.className = 'view';
    section.setAttribute('aria-label', 'Cenários hipotéticos');

    main.insertBefore(section, main.querySelector(':scope > footer'));

    let frame;

    button.addEventListener('click', () => {
      if (typeof window.showTab !== 'function') {
        window.location.href = '/hypotheses';
        return;
      }

      if (!frame) {
        frame = document.createElement('iframe');
        frame.src = '/hypotheses';
        frame.title = 'Cenários hipotéticos da carreira';
        frame.height = '1200';
        section.appendChild(frame);
      }

      window.showTab('hypotheses');
    });

    const sync = () =>
      document.body.classList.toggle('hypothesis-open', section.classList.contains('active'));

    new MutationObserver(sync).observe(section, {
      attributes: true,
      attributeFilter: ['class'],
    });

    window.addEventListener('message', (event) => {
      if (
        !frame ||
        event.origin !== window.location.origin ||
        event.source !== frame.contentWindow ||
        event.data?.type !== 'hypothesis:height'
      )
        return;

      const height = Number(event.data.height);
      if (Number.isFinite(height) && height >= 300 && height <= 30000) {
        frame.height = String(Math.ceil(height));
      }
    });

    sync();
  }

  function installPage() {
    const profileFrame = $('#hyp-profile');
    const status = $('#hyp-profile-status');
    const cards = $$('.hyp-card');
    let profileWindow;
    let profileForm;
    let initializing = false;

    for (const card of cards) {
      const levels =
        card.dataset.kind === 'level_vi'
          ? ['I', 'II', 'III', 'IV', 'V', 'VI']
          : ['I', 'II', 'III', 'IV', 'V'];

      $('.hyp-position', card).innerHTML = `
        <div class="hyp-form-grid">
          <label>Nível simulado
            <select data-param="level">
              <option value="">Mesmo nível do vínculo</option>
              ${levels.map((level) => `<option value="${level}">${level}</option>`).join('')}
            </select>
          </label>
          <label>Grau simulado
            <select data-param="grade">
              <option value="">Mesmo grau do vínculo</option>
              ${[...'ABCDEFGHIJ']
                .map((grade) => `<option value="${grade}">${grade}</option>`)
                .join('')}
            </select>
          </label>
        </div>`;

      $('.hyp-calculate', card).addEventListener('click', () => run(card, true));

      card.addEventListener('input', () => schedule(card));
      card.addEventListener('change', () => schedule(card));
    }

    function schedule(card) {
      card._sequence = (card._sequence || 0) + 1;
      clearTimeout(card._timer);
      $('.hyp-calculate', card).disabled = false;
      $('.hyp-result', card).textContent = 'Atualizando a simulação…';
      card._timer = setTimeout(() => run(card), 650);
    }

    function scheduleAll() {
      cards.forEach(schedule);
    }

    function readScenario(report) {
      if (!profileWindow || !profileForm) {
        throw new Error('Aguarde o carregamento dos dados do vínculo.');
      }

      if (!profileForm.checkValidity()) {
        if (report) profileForm.reportValidity();
        throw new Error('Complete os dados do vínculo para calcular.');
      }

      const scenario = profileWindow.scenario();

      if (!scenario.level || !scenario.grade) {
        throw new Error('A tabela da carreira ainda não está disponível.');
      }

      return scenario;
    }

    async function run(card, report = false) {
      const sequence = (card._sequence = (card._sequence || 0) + 1);
      const output = $('.hyp-result', card);
      const button = $('.hyp-calculate', card);

      try {
        const scenario = readScenario(report);
        const controls = $$('[data-param]', card);

        for (const input of controls) {
          if (!input.checkValidity()) {
            if (report) input.reportValidity();
            throw new Error('Confira os valores deste cenário.');
          }
        }

        const body = {
          scenario,
          kind: card.dataset.kind,
          level: $('[data-param="level"]', card).value || null,
          grade: $('[data-param="grade"]', card).value || null,
        };

        const combine = $('[data-param="combine_gdpi"]', card);
        const increase = $('[data-param="increase_percent"]', card);
        const months = $('[data-param="months"]', card);

        if (combine) body.combine_gdpi = combine.checked;
        if (increase) body.increase_percent = increase.value;
        if (months) body.months = Number(months.value);

        button.disabled = true;
        output.textContent =
          body.kind === 'inflation' ? 'Consultando o IPCA e calculando…' : 'Calculando…';

        const response = await fetch('/api/hypotheses', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        const result = await response.json();

        if (!response.ok) {
          let message = result.detail;

          if (Array.isArray(message)) {
            message = message
              .map((item) =>
                String(item.msg || 'Confira os dados informados.').replace(/^Value error, /, ''),
              )
              .join(' · ');
          }

          throw new Error(
            typeof message === 'string' ? message : 'Não foi possível calcular este cenário.',
          );
        }

        if (sequence !== card._sequence) return;

        render(card, result);
      } catch (error) {
        if (sequence === card._sequence) {
          output.innerHTML = `<p class="hyp-error" role="alert">
            ${esc(error.message)}
          </p>`;
        }
      } finally {
        if (sequence === card._sequence) button.disabled = false;
      }
    }

    function render(card, result) {
      const output = $('.hyp-result', card);
      const monthly = result.monthly;
      const hypothesis = result.hypothesis;

      const metric = (label, value) => `
        <div class="hyp-metric">
          <span>${esc(label)}</span><strong>${value}</strong>
        </div>`;

      const difference = hypothesis.difference.monthly_net;
      const signedDifference = `${Number(difference) > 0 ? '+' : ''}${currency(difference)}`;

      const inflation = hypothesis.inflation;
      const inflationMarkup = inflation
        ? `
        <p class="hyp-small">
          IPCA acumulado: <strong>
            ${number(inflation.rate_percent)}%
          </strong><br>
          ${monthLabel(inflation.from)} a
          ${monthLabel(inflation.through)}<br>
          <a href="${esc(inflation.source_url)}"
             target="_blank" rel="noopener noreferrer">
            Fonte: Banco Central
          </a>
        </p>`
        : '';

      output.innerHTML = `
        <p class="hyp-small">
          Posição simulada:
          ${esc(result.scenario.level)}-${esc(result.scenario.grade)}
        </p>
        <div class="hyp-net">${currency(monthly.net)}</div>

        ${metric('Bruto mensal', currency(monthly.gross))}
        ${metric('Descontos', currency(monthly.deductions))}
        ${metric('Diferença líquida mensal', signedDifference)}
        ${result.annual ? metric('Líquido anual estimado', currency(result.annual.net)) : ''}

        ${inflationMarkup}

        <details>
          <summary>Composição do cálculo</summary>
          ${monthly.earnings.map((item) => metric(item.name, currency(item.amount))).join('')}
          ${metric('RPPS', currency(monthly.pension.amount))}
          ${metric('IPSEMG', currency(monthly.health.amount))}
          ${metric('IRRF', currency(monthly.income_tax.amount))}
          ${metric('Descontos totais', currency(monthly.deductions))}
          ${metric('Líquido', currency(monthly.net))}
        </details>

        <details>
          <summary>Hipóteses consideradas</summary>
          <p class="hyp-small">
            Referência da comparação:
            ${esc(hypothesis.baseline.level)}-${esc(hypothesis.baseline.grade)},
            líquido ${currency(hypothesis.baseline.monthly_net)}.
          </p>
          <ul class="hyp-small">
            ${hypothesis.assumptions.map((item) => `<li>${esc(item)}</li>`).join('')}
          </ul>
        </details>

        <button class="hyp-download" type="button">
          Baixar memória do cálculo
        </button>`;

      $('.hyp-download', output).addEventListener('click', () => {
        const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });

        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `cenario-hipotetico-${card.dataset.kind}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1500);
      });
    }

    function parentScenario() {
      try {
        const form = window.parent.document.querySelector('#scenario-form');

        if (
          window.parent !== window &&
          form?.checkValidity() &&
          typeof window.parent.scenario === 'function'
        ) {
          return JSON.parse(JSON.stringify(window.parent.scenario()));
        }
      } catch {
        // O formulário local continua disponível sem copiar o painel externo.
      }

      return null;
    }

    async function initializeProfile() {
      if (initializing) return;

      const frameWindow = profileFrame.contentWindow;
      let doc;

      try {
        doc = frameWindow.document;
      } catch {
        status.textContent =
          'Não foi possível acessar a Calculadora. Confira os cabeçalhos de segurança.';
        status.classList.add('hyp-error');
        return;
      }

      // Aguarda o carregamento da página real do formulário.
      if (!doc || doc.URL === 'about:blank' || doc.readyState !== 'complete') {
        return;
      }

      initializing = true;

      try {
        profileWindow = frameWindow;
        profileForm = doc.querySelector('#scenario-form');

        if (!profileForm || typeof profileWindow.scenario !== 'function') {
          throw new Error('O formulário da Calculadora não foi encontrado na página carregada.');
        }

        doc.documentElement.classList.add('hyp-profile');
        stylesheet(doc);

        const scenario = parentScenario();

        if (scenario && typeof profileWindow.loadScenario === 'function') {
          await profileWindow.loadScenario(scenario);
        } else if (typeof profileWindow.loadParameters === 'function') {
          await profileWindow.loadParameters();
        }

        profileForm.addEventListener('input', scheduleAll);
        profileForm.addEventListener('change', scheduleAll);
        profileForm.addEventListener('submit', scheduleAll);

        status.classList.remove('hyp-error');
        status.textContent = 'Os dados deste painel são usados nos quatro cenários.';

        cards.forEach((card) => run(card));
      } catch (error) {
        status.textContent = 'Não foi possível carregar os dados do vínculo. ' + error.message;
        status.classList.add('hyp-error');
      } finally {
        initializing = false;
      }
    }

    profileFrame.addEventListener('load', initializeProfile);

    try {
      if (profileFrame.contentDocument?.readyState === 'complete') {
        initializeProfile();
      }
    } catch {
      // O evento load fará a inicialização quando o formulário estiver pronto.
    }

    $('#hyp-copy').addEventListener('click', async () => {
      const scenario = parentScenario();

      if (!scenario || !profileWindow) {
        status.textContent = 'Complete os dados na Calculadora antes de copiá-los.';
        return;
      }

      try {
        await profileWindow.loadScenario(scenario);
        status.textContent = 'Dados da Calculadora copiados para este painel.';
        scheduleAll();
      } catch {
        status.textContent = 'Não foi possível copiar os dados.';
      }
    });

    let lastHeight = 0;

    new ResizeObserver(() => {
      const height = Math.ceil(document.body.scrollHeight + 30);

      if (Math.abs(height - lastHeight) < 5) return;
      lastHeight = height;

      if (window.parent !== window) {
        window.parent.postMessage({ type: 'hypothesis:height', height }, window.location.origin);
      }
    }).observe(document.body);
  }

  if ($('#hypothesis-app')) {
    installPage();
  } else if (window.top === window) {
    installTab();
  }
})();
