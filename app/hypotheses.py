"""Cenários hipotéticos, separados das tabelas oficiais persistidas."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from time import monotonic
from typing import Literal
from urllib.request import Request as URLRequest, urlopen

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .calculator import CalculationError, calculate, money
from .database import resolve_parameters
from .schemas import Parameters, Position, Scenario


router = APIRouter()
D = Decimal

BCB_URL = (
    "https://api.bcb.gov.br/dados/serie/"
    "bcdata.sgs.433/dados/ultimos/12?formato=json"
)

LEVEL_VI = (
    ("A", "13084.58", "3104"),
    ("B", "13415.22", "3138"),
    ("C", "13754.19", "3172"),
    ("D", "14101.71", "3206"),
    ("E", "14457.99", "3240"),
    ("F", "14823.25", "3274"),
    ("G", "15197.70", "3308"),
    ("H", "15581.59", "3342"),
    ("I", "15975.15", "3376"),
    ("J", "16378.63", "3410"),
)

TITLES = {
    "level_vi": "Criação do nível VI",
    "incorporation": "Incorporação total da GDPI",
    "increase": "Aumento do vencimento básico",
    "inflation": "Reposição inflacionária",
}


class HypothesisRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )

    scenario: Scenario
    kind: Literal["level_vi", "incorporation", "increase", "inflation"]

    level: Literal["I", "II", "III", "IV", "V", "VI"] | None = None
    grade: str | None = Field(default=None, pattern=r"^[A-J]$")

    combine_gdpi: bool = False
    increase_percent: Decimal = Field(default=D("10"), ge=0, le=1000)
    months: int = Field(default=12, ge=1, le=12)

    @model_validator(mode="after")
    def coherent(self):
        if self.scenario.mode not in ("real", "official"):
            raise ValueError("Utilize os dados reais da carreira.")

        if self.level == "VI" and self.kind != "level_vi":
            raise ValueError(
                "O nível VI está disponível no cenário de criação desse nível."
            )

        if self.combine_gdpi and self.kind != "level_vi":
            raise ValueError(
                "A combinação com incorporação está disponível no cenário do nível VI."
            )

        return self


class InflationUnavailable(ValueError):
    pass


@lru_cache(maxsize=2)
def _published_ipca(hour_bucket):
    """Consulta somente a série pública fixa do IPCA; cache de até uma hora."""
    try:
        request = URLRequest(
            BCB_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 Horizonte-EPPGG/1.0",
            },
        )

        with urlopen(request, timeout=15) as response:
            raw = response.read(1_000_001)

        if len(raw) > 1_000_000:
            raise ValueError("Resposta maior que o esperado.")

        payload = json.loads(raw)
        if not isinstance(payload, list) or len(payload) != 12:
            raise ValueError("Quantidade inesperada de observações.")

        observations = []

        for item in payload:
            month = datetime.strptime(
                item["data"], "%d/%m/%Y"
            ).date().replace(day=1)

            rate = D(str(item["valor"]).replace(",", "."))

            if not rate.is_finite() or rate <= -100:
                raise ValueError("Índice mensal inválido.")

            observations.append((month, rate))

        observations.sort(key=lambda item: item[0])

        for previous, current in zip(observations, observations[1:]):
            previous_number = previous[0].year * 12 + previous[0].month
            current_number = current[0].year * 12 + current[0].month

            if current_number - previous_number != 1:
                raise ValueError("A série contém meses ausentes ou repetidos.")

        fetched_at = datetime.now(timezone.utc).isoformat()
        return tuple(observations), fetched_at

    except Exception as exc:
        raise InflationUnavailable(
            "Não foi possível consultar o IPCA no Banco Central. "
            "Tente novamente mais tarde. Os demais cenários continuam disponíveis."
        ) from exc


def accumulated_ipca(months):
    observations, fetched_at = _published_ipca(int(monotonic() // 3600))
    selected = observations[-months:]

    factor = D("1")
    for _, rate in selected:
        factor *= D("1") + rate / 100

    return {
        "name": "IPCA",
        "series": 433,
        "source_url": BCB_URL,
        "months": months,
        "from": selected[0][0].isoformat(),
        "through": selected[-1][0].isoformat(),
        "factor": str(factor),
        "rate_percent": str((factor - 1) * 100),
        "fetched_at": fetched_at,
        "observations": [
            {"month": month.isoformat(), "rate_percent": str(rate)}
            for month, rate in selected
        ],
    }


def reference_salary(parameters, with_level_vi):
    last_level = "VI" if with_level_vi else "V"

    position = next(
        (
            item
            for item in parameters.positions
            if item.level == last_level and item.grade == "J"
        ),
        None,
    )

    if position is None:
        raise CalculationError(
            "O último nível e grau não estão cadastrados na tabela."
        )

    return position.salary


@router.post("/api/hypotheses")
def run_hypothesis(body: HypothesisRequest, request: Request):
    """Calcula em cópias dos parâmetros; não grava hipóteses no banco."""
    try:
        with request.app.state.sessions() as session:
            original = resolve_parameters(
                session, body.scenario.competence, "real"
            )

        if not isinstance(original, Parameters) or original.status != "verified":
            raise CalculationError(
                "Não há tabelas completas de descontos para esta competência."
            )

        baseline = calculate(body.scenario, original)
        parameters = original.model_copy(deep=True)

        with_level_vi = body.kind == "level_vi"
        incorporate = (
            body.kind == "incorporation"
            or with_level_vi and body.combine_gdpi
        )

        assumptions = [
            "Simulação hipotética, sem alteração das tabelas vigentes.",
            (
                "Comissões, funções, tabelas de descontos e teto previdenciário "
                "permanecem nos valores da competência escolhida."
            ),
            (
                "As diferenças são comparadas ao vínculo de referência "
                "preenchido no painel."
            ),
        ]

        if with_level_vi:
            parameters.positions.extend(
                Position(
                    level="VI",
                    grade=grade,
                    salary=D(salary),
                    points=D(points),
                )
                for grade, salary, points in LEVEL_VI
            )

            assumptions.append(
                "O vencimento VI-J, de R$ 16.378,63, passa a ser "
                "a referência da GDPI em todos os níveis."
            )

        inflation = None
        factor = D("1")

        if body.kind == "increase":
            factor += body.increase_percent / 100
            assumptions.append(
                f"Aumento de {body.increase_percent}% em todos os "
                "vencimentos básicos, com atualização da referência da GDPI."
            )

        elif body.kind == "inflation":
            inflation = accumulated_ipca(body.months)
            factor = D(inflation["factor"])

            assumptions.append(
                "Reposição pelo IPCA dos últimos meses publicados, "
                "com acumulação composta. O período utilizado aparece no resultado."
            )

        if factor != 1:
            parameters.positions = [
                position.model_copy(
                    update={"salary": money(position.salary * factor)}
                )
                for position in parameters.positions
            ]

        parameters.gdpi_reference_salary = reference_salary(
            parameters, with_level_vi
        )
        reference_before_incorporation = parameters.gdpi_reference_salary

        incorporated = {}

        if incorporate:
            positions = []

            for position in parameters.positions:
                amount = money(
                    position.points
                    * parameters.gdpi_point_share
                    * parameters.gdpi_factor
                    * parameters.gdpi_reference_salary
                )

                incorporated[f"{position.level}-{position.grade}"] = amount

                positions.append(
                    position.model_copy(
                        update={"salary": money(position.salary + amount)}
                    )
                )

            parameters.positions = positions
            parameters.gdpi_factor = D("0")
            parameters.gdpi_reference_salary = reference_salary(
                parameters, with_level_vi
            )

            assumptions.append(
                "Incorporação de 100% da GDPI máxima de cada posição "
                "ao vencimento básico, sem parcela variável e sem redução por nota."
            )

            if body.scenario.remuneration_option == "a":
                assumptions.append(
                    "Na opção A, permanece a substituição do vencimento "
                    "do cargo efetivo pelo vencimento comissionado."
                )

        if (
            body.scenario.ade_base is not None
            or body.scenario.quinquennium_base is not None
        ):
            assumptions.append(
                "As bases específicas informadas para adicionais pessoais "
                "permanecem fixas."
            )

        scenario = body.scenario.model_copy(
            update={
                "level": body.level or body.scenario.level,
                "grade": body.grade or body.scenario.grade,
            }
        )

        parameters.version = (
            f"hipotese-{body.kind}-{original.version}"
        )[:100]

        parameters.status = "provisional"
        parameters.verified_at = None
        parameters.supersedes = []
        parameters.source = (
            "Simulação de alteração da carreira; descontos da competência "
            "de referência."
        )
        parameters.sources["salary"] = (
            "Vencimento básico de cenário hipotético."
        )
        parameters.sources["gdpi"] = (
            "GDPI recalculada conforme as hipóteses descritas na memória."
        )
        parameters.notes = [*parameters.notes, *assumptions]

        result = calculate(scenario, parameters)
        result["parameters"]["status"] = "hypothetical"
        result["warnings"] = [
            "CENÁRIO HIPOTÉTICO — não representa alteração legal vigente.",
            *[
                warning
                for warning in result["warnings"]
                if not warning.startswith("SIMULAÇÃO PROVISÓRIA")
            ],
        ]

        title = TITLES[body.kind]
        if with_level_vi and incorporate:
            title += " + incorporação total da GDPI"

        annual_difference = None
        if result["annual"] and baseline["annual"]:
            annual_difference = money(
                result["annual"]["net"] - baseline["annual"]["net"]
            )

        result["hypothesis"] = {
            "title": title,
            "input": body.model_dump(mode="json"),
            "official_version": original.version,
            "assumptions": assumptions,
            "gdpi_reference_before_incorporation": (
                reference_before_incorporation
            ),
            "incorporated_amount": incorporated.get(
                f"{scenario.level}-{scenario.grade}", D("0")
            ),
            "inflation": inflation,
            "baseline": {
                "level": body.scenario.level,
                "grade": body.scenario.grade,
                "monthly_gross": baseline["monthly"]["gross"],
                "monthly_net": baseline["monthly"]["net"],
                "annual_net": (
                    baseline["annual"]["net"]
                    if baseline["annual"]
                    else None
                ),
            },
            "difference": {
                "monthly_net": money(
                    result["monthly"]["net"] - baseline["monthly"]["net"]
                ),
                "annual_net": annual_difference,
            },
        }

        return jsonable_encoder(
            result, custom_encoder={Decimal: lambda value: str(value)}
        )

    except InflationUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except CalculationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/hypotheses", response_class=HTMLResponse)
def hypotheses_page():
    rows = []

    for grade, salary, points in LEVEL_VI:
        formatted_salary = (
            f"{D(salary):,.2f}"
            .replace(",", "_")
            .replace(".", ",")
            .replace("_", ".")
        )

        rows.append(
            f"<tr><td>{grade}</td><td>R$ {formatted_salary}</td>"
            f"<td>{points}</td><td>{int(points) // 2}</td></tr>"
        )

    return HTMLResponse(HTML.replace("@@LEVEL_VI_ROWS@@", "".join(rows)))


@router.get("/hypotheses.js")
def hypotheses_javascript():
    return Response(
        JS,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/hypotheses.css")
def hypotheses_stylesheet():
    return Response(
        CSS,
        media_type="text/css",
        headers={"Cache-Control": "no-cache"},
    )


HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Cenários hipotéticos · Horizonte</title>
  <link rel="stylesheet" href="/hypotheses.css">
  <script src="/hypotheses.js" defer></script>
</head>
<body class="hyp-page">
<main id="hypothesis-app">
  <div class="hyp-heading">
    <div>
      <h1>Cenários hipotéticos</h1>
      <p>Explore possíveis mudanças na remuneração da carreira.</p>
    </div>
    <button id="hyp-copy" type="button">
      Usar dados da Calculadora
    </button>
  </div>

  <p class="hyp-notice">
    As hipóteses abaixo não representam mudanças legais vigentes.
    A incorporação considera a GDPI máxima de cada posição.
  </p>

  <div class="hyp-layout">
    <aside class="hyp-sidebar">
      <h2>Dados do vínculo</h2>
      <p id="hyp-profile-status" role="status">
        Carregando os dados da carreira…
      </p>
      <iframe
        id="hyp-profile"
        src="/"
        title="Dados do vínculo para os cenários hipotéticos"
        height="1050"
      ></iframe>
    </aside>

    <div class="hyp-grid">
      <article class="hyp-card" data-kind="level_vi">
        <h2>1. Criação do nível VI</h2>
        <p>
          Inclui o novo nível e utiliza o VI-J como referência
          da GDPI de toda a carreira.
        </p>

        <div class="hyp-position"></div>

        <label class="hyp-check">
          <input type="checkbox" data-param="combine_gdpi">
          Também incorporar toda a GDPI
        </label>

        <details>
          <summary>Tabela hipotética do nível VI</summary>
          <div class="hyp-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Grau</th>
                  <th>VB</th>
                  <th>Pontos</th>
                  <th>Variáveis · 50%</th>
                </tr>
              </thead>
              <tbody>@@LEVEL_VI_ROWS@@</tbody>
            </table>
          </div>
        </details>

        <button class="hyp-calculate" type="button">
          Calcular cenário
        </button>
        <div class="hyp-result" aria-live="polite"></div>
      </article>

      <article class="hyp-card" data-kind="incorporation">
        <h2>2. Incorporação total da GDPI</h2>
        <p>
          A GDPI máxima passa a integrar o vencimento básico.
          Não permanece parcela variável.
        </p>

        <div class="hyp-position"></div>

        <button class="hyp-calculate" type="button">
          Calcular cenário
        </button>
        <div class="hyp-result" aria-live="polite"></div>
      </article>

      <article class="hyp-card" data-kind="increase">
        <h2>3. Aumento do vencimento básico</h2>
        <p>
          Aplica o percentual à tabela de vencimentos e
          atualiza a referência da GDPI.
        </p>

        <div class="hyp-position"></div>

        <label>
          Aumento (%)
          <input
            data-param="increase_percent"
            type="number"
            min="0"
            max="1000"
            step="0.01"
            value="10"
            required
          >
        </label>

        <button class="hyp-calculate" type="button">
          Calcular cenário
        </button>
        <div class="hyp-result" aria-live="polite"></div>
      </article>

      <article class="hyp-card" data-kind="inflation">
        <h2>4. Reposição inflacionária</h2>
        <p>
          Atualiza o vencimento básico e a referência da GDPI
          pelo IPCA dos últimos meses publicados.
        </p>

        <div class="hyp-position"></div>

        <label>
          Período
          <select data-param="months">
            <option value="1">1 mês</option>
            <option value="2">2 meses</option>
            <option value="3">3 meses</option>
            <option value="4">4 meses</option>
            <option value="5">5 meses</option>
            <option value="6">6 meses</option>
            <option value="7">7 meses</option>
            <option value="8">8 meses</option>
            <option value="9">9 meses</option>
            <option value="10">10 meses</option>
            <option value="11">11 meses</option>
            <option value="12" selected>12 meses</option>
          </select>
        </label>

        <button class="hyp-calculate" type="button">
          Calcular cenário
        </button>
        <div class="hyp-result" aria-live="polite"></div>
      </article>
    </div>
  </div>
</main>
</body>
</html>
"""


CSS = r"""
.topbar .tabs {
  display: flex;
  flex-wrap: wrap;
  min-width: 0;
}
body.hypothesis-open #save {
  visibility: hidden;
  pointer-events: none;
}
#hypotheses > iframe {
  display: block;
  width: 100%;
  border: 0;
}
.hyp-page {
  margin: 0;
  padding: 14px;
  background: #f4f7f6;
  color: #173d37;
  font: 14px/1.5 system-ui, sans-serif;
}
.hyp-page * { box-sizing: border-box; }
.hyp-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.hyp-page h1 { margin: 0; font-size: 25px; }
.hyp-page h2 { margin: 0 0 10px; font-size: 18px; }
.hyp-page p { color: #536a64; }
.hyp-notice {
  padding: 12px 15px;
  border: 1px solid #d9e6df;
  border-radius: 10px;
  background: #fff;
}
.hyp-layout {
  display: grid;
  grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
  align-items: start;
  gap: 18px;
}
.hyp-sidebar, .hyp-card {
  min-width: 0;
  padding: 18px;
  border: 1px solid #dce7e1;
  border-radius: 14px;
  background: #fff;
}
.hyp-sidebar > iframe {
  display: block;
  width: 100%;
  border: 0;
}
.hyp-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 16px;
}
.hyp-page label {
  display: block;
  margin: 10px 0;
  font-size: 13px;
  font-weight: 600;
}
.hyp-page input, .hyp-page select {
  display: block;
  width: 100%;
  min-width: 0;
  margin-top: 5px;
  padding: 10px;
  border: 1px solid #cadbd2;
  border-radius: 8px;
  background: #fff;
  color: #173d37;
  font: inherit;
}
.hyp-page button {
  padding: 10px 14px;
  border: 0;
  border-radius: 8px;
  background: #115e59;
  color: #fff;
  font: inherit;
  cursor: pointer;
}
.hyp-page button:disabled {
  opacity: .55;
  cursor: wait;
}
.hyp-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.hyp-page .hyp-check {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hyp-page .hyp-check input {
  width: auto;
  margin: 0;
}
.hyp-page details { margin: 14px 0; }
.hyp-page summary { cursor: pointer; font-weight: 600; }
.hyp-table-scroll { overflow-x: auto; }
.hyp-page table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.hyp-page th, .hyp-page td {
  padding: 8px 5px;
  border-bottom: 1px solid #e4ece7;
  text-align: right;
}
.hyp-page th:first-child, .hyp-page td:first-child {
  text-align: left;
}
.hyp-calculate { width: 100%; margin-top: 12px; }
.hyp-result { margin-top: 15px; }
.hyp-net {
  margin: 8px 0 14px;
  font-size: 28px;
  font-weight: 750;
  color: #115e59;
}
.hyp-metric {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 0;
  border-bottom: 1px solid #edf2ee;
}
.hyp-metric strong { text-align: right; white-space: nowrap; }
.hyp-error { color: #9e3030 !important; }
.hyp-small { font-size: 12px; color: #536a64; }
.hyp-page .hyp-download {
  margin-top: 12px;
  background: #e6f1ea;
  color: #115e59;
}
html.hyp-profile header,
html.hyp-profile footer,
html.hyp-profile .skip,
html.hyp-profile .output-panel {
  display: none !important;
}
html.hyp-profile body {
  margin: 0 !important;
  padding: 0 !important;
  background: #fff !important;
}
html.hyp-profile #main {
  width: 100% !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
}
html.hyp-profile .workspace {
  display: block !important;
}
html.hyp-profile .input-panel {
  position: static !important;
  width: 100% !important;
  max-width: none !important;
  padding: 0 !important;
  border: 0 !important;
  box-shadow: none !important;
}
@media (max-width: 1150px) {
  .hyp-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 760px) {
  .hyp-layout { grid-template-columns: minmax(0, 1fr); }
  .hyp-page { padding: 8px; }
}
"""


JS = r"""
(() => {
  "use strict";

  const $ = (selector, node = document) => node.querySelector(selector);
  const $$ = (selector, node = document) =>
    [...node.querySelectorAll(selector)];

  const esc = value => String(value ?? "").replace(
    /[&<>"']/g,
    character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;",
      '"': "&quot;", "'": "&#39;"
    })[character]
  );

  const currency = value => value == null ? "—" :
    new Intl.NumberFormat("pt-BR", {
      style: "currency", currency: "BRL"
    }).format(Number(value));

  const number = value => new Intl.NumberFormat("pt-BR", {
    maximumFractionDigits: 4
  }).format(Number(value));

  const monthLabel = value => {
    const [year, month] = value.split("-");
    return `${month}/${year}`;
  };

  function stylesheet(doc) {
    if (doc.getElementById("hypothesis-stylesheet")) return;
    const link = doc.createElement("link");
    link.id = "hypothesis-stylesheet";
    link.rel = "stylesheet";
    link.href = "/hypotheses.css";
    doc.head.appendChild(link);
  }

  function installTab() {
    const tabs = $("header .tabs");
    const main = $("#main");
    if (!tabs || !main || $("#hypotheses")) return;

    stylesheet(document);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "tab";
    button.dataset.tab = "hypotheses";
    button.textContent = "Cenários hipotéticos";
    tabs.appendChild(button);

    const section = document.createElement("section");
    section.id = "hypotheses";
    section.className = "view";
    section.setAttribute("aria-label", "Cenários hipotéticos");

    main.insertBefore(section, main.querySelector(":scope > footer"));

    let frame;

    button.addEventListener("click", () => {
      if (typeof window.showTab !== "function") {
        window.location.href = "/hypotheses";
        return;
      }

      if (!frame) {
        frame = document.createElement("iframe");
        frame.src = "/hypotheses";
        frame.title = "Cenários hipotéticos da carreira";
        frame.height = "1200";
        section.appendChild(frame);
      }

      window.showTab("hypotheses");
    });

    const sync = () => document.body.classList.toggle(
      "hypothesis-open", section.classList.contains("active")
    );

    new MutationObserver(sync).observe(section, {
      attributes: true,
      attributeFilter: ["class"]
    });

    window.addEventListener("message", event => {
      if (
        !frame ||
        event.origin !== window.location.origin ||
        event.source !== frame.contentWindow ||
        event.data?.type !== "hypothesis:height"
      ) return;

      const height = Number(event.data.height);
      if (Number.isFinite(height) && height >= 300 && height <= 30000) {
        frame.height = String(Math.ceil(height));
      }
    });

    sync();
  }

  function installPage() {
    const profileFrame = $("#hyp-profile");
    const status = $("#hyp-profile-status");
    const cards = $$(".hyp-card");
    let profileWindow;
    let profileForm;
    let initializing = false;

    for (const card of cards) {
      const levels = card.dataset.kind === "level_vi"
        ? ["I", "II", "III", "IV", "V", "VI"]
        : ["I", "II", "III", "IV", "V"];

      $(".hyp-position", card).innerHTML = `
        <div class="hyp-form-grid">
          <label>Nível simulado
            <select data-param="level">
              <option value="">Mesmo nível do vínculo</option>
              ${levels.map(level =>
                `<option value="${level}">${level}</option>`
              ).join("")}
            </select>
          </label>
          <label>Grau simulado
            <select data-param="grade">
              <option value="">Mesmo grau do vínculo</option>
              ${[..."ABCDEFGHIJ"].map(grade =>
                `<option value="${grade}">${grade}</option>`
              ).join("")}
            </select>
          </label>
        </div>`;

      $(".hyp-calculate", card).addEventListener(
        "click", () => run(card, true)
      );

      card.addEventListener("input", () => schedule(card));
      card.addEventListener("change", () => schedule(card));
    }

    function schedule(card) {
      card._sequence = (card._sequence || 0) + 1;
      clearTimeout(card._timer);
      $(".hyp-calculate", card).disabled = false;
      $(".hyp-result", card).textContent = "Atualizando a simulação…";
      card._timer = setTimeout(() => run(card), 650);
    }

    function scheduleAll() {
      cards.forEach(schedule);
    }

    function readScenario(report) {
      if (!profileWindow || !profileForm) {
        throw new Error("Aguarde o carregamento dos dados do vínculo.");
      }

      if (!profileForm.checkValidity()) {
        if (report) profileForm.reportValidity();
        throw new Error("Complete os dados do vínculo para calcular.");
      }

      const scenario = profileWindow.scenario();

      if (!scenario.level || !scenario.grade) {
        throw new Error("A tabela da carreira ainda não está disponível.");
      }

      return scenario;
    }

    async function run(card, report = false) {
      const sequence = card._sequence = (card._sequence || 0) + 1;
      const output = $(".hyp-result", card);
      const button = $(".hyp-calculate", card);

      try {
        const scenario = readScenario(report);
        const controls = $$("[data-param]", card);

        for (const input of controls) {
          if (!input.checkValidity()) {
            if (report) input.reportValidity();
            throw new Error("Confira os valores deste cenário.");
          }
        }

        const body = {
          scenario,
          kind: card.dataset.kind,
          level: $('[data-param="level"]', card).value || null,
          grade: $('[data-param="grade"]', card).value || null
        };

        const combine = $('[data-param="combine_gdpi"]', card);
        const increase = $('[data-param="increase_percent"]', card);
        const months = $('[data-param="months"]', card);

        if (combine) body.combine_gdpi = combine.checked;
        if (increase) body.increase_percent = increase.value;
        if (months) body.months = Number(months.value);

        button.disabled = true;
        output.textContent = body.kind === "inflation"
          ? "Consultando o IPCA e calculando…"
          : "Calculando…";

        const response = await fetch("/api/hypotheses", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body)
        });

        const result = await response.json();

        if (!response.ok) {
          let message = result.detail;

          if (Array.isArray(message)) {
            message = message.map(item =>
              String(item.msg || "Confira os dados informados.")
                .replace(/^Value error, /, "")
            ).join(" · ");
          }

          throw new Error(
            typeof message === "string"
              ? message
              : "Não foi possível calcular este cenário."
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
      const output = $(".hyp-result", card);
      const monthly = result.monthly;
      const hypothesis = result.hypothesis;

      const metric = (label, value) => `
        <div class="hyp-metric">
          <span>${esc(label)}</span><strong>${value}</strong>
        </div>`;

      const difference = hypothesis.difference.monthly_net;
      const signedDifference =
        `${Number(difference) > 0 ? "+" : ""}${currency(difference)}`;

      const inflation = hypothesis.inflation;
      const inflationMarkup = inflation ? `
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
        </p>` : "";

      output.innerHTML = `
        <p class="hyp-small">
          Posição simulada:
          ${esc(result.scenario.level)}-${esc(result.scenario.grade)}
        </p>
        <div class="hyp-net">${currency(monthly.net)}</div>

        ${metric("Bruto mensal", currency(monthly.gross))}
        ${metric("Descontos", currency(monthly.deductions))}
        ${metric("Diferença líquida mensal", signedDifference)}
        ${result.annual
          ? metric("Líquido anual estimado", currency(result.annual.net))
          : ""}

        ${inflationMarkup}

        <details>
          <summary>Composição do cálculo</summary>
          ${monthly.earnings.map(item =>
            metric(item.name, currency(item.amount))
          ).join("")}
          ${metric("RPPS", currency(monthly.pension.amount))}
          ${metric("IPSEMG", currency(monthly.health.amount))}
          ${metric("IRRF", currency(monthly.income_tax.amount))}
          ${metric("Descontos totais", currency(monthly.deductions))}
          ${metric("Líquido", currency(monthly.net))}
        </details>

        <details>
          <summary>Hipóteses consideradas</summary>
          <p class="hyp-small">
            Referência da comparação:
            ${esc(hypothesis.baseline.level)}-${esc(hypothesis.baseline.grade)},
            líquido ${currency(hypothesis.baseline.monthly_net)}.
          </p>
          <ul class="hyp-small">
            ${hypothesis.assumptions.map(item =>
              `<li>${esc(item)}</li>`
            ).join("")}
          </ul>
        </details>

        <button class="hyp-download" type="button">
          Baixar memória do cálculo
        </button>`;

      $(".hyp-download", output).addEventListener("click", () => {
        const blob = new Blob(
          [JSON.stringify(result, null, 2)],
          {type: "application/json"}
        );

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
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
        const form = window.parent.document.querySelector("#scenario-form");

        if (
          window.parent !== window &&
          form?.checkValidity() &&
          typeof window.parent.scenario === "function"
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
          "Não foi possível acessar a Calculadora. Confira os cabeçalhos de segurança.";
        status.classList.add("hyp-error");
        return;
      }
    
      // Aguarda o carregamento da página real do formulário.
      if (
        !doc ||
        doc.URL === "about:blank" ||
        doc.readyState !== "complete"
      ) {
        return;
      }
    
      initializing = true;
    
      try {
        profileWindow = frameWindow;
        profileForm = doc.querySelector("#scenario-form");
    
        if (
          !profileForm ||
          typeof profileWindow.scenario !== "function"
        ) {
          throw new Error(
            "O formulário da Calculadora não foi encontrado na página carregada."
          );
        }
    
        doc.documentElement.classList.add("hyp-profile");
        stylesheet(doc);
    
        const scenario = parentScenario();
    
        if (
          scenario &&
          typeof profileWindow.loadScenario === "function"
        ) {
          await profileWindow.loadScenario(scenario);
        } else if (
          typeof profileWindow.loadParameters === "function"
        ) {
          await profileWindow.loadParameters();
        }
    
        profileForm.addEventListener("input", scheduleAll);
        profileForm.addEventListener("change", scheduleAll);
        profileForm.addEventListener("submit", scheduleAll);
    
        status.classList.remove("hyp-error");
        status.textContent =
          "Os dados deste painel são usados nos quatro cenários.";
    
        cards.forEach(card => run(card));
      } catch (error) {
        status.textContent =
          "Não foi possível carregar os dados do vínculo. " +
          error.message;
        status.classList.add("hyp-error");
      } finally {
        initializing = false;
      }
    }

    profileFrame.addEventListener("load", initializeProfile);

    try {
      if (profileFrame.contentDocument?.readyState === "complete") {
        initializeProfile();
      }
    } catch {
      // O evento load fará a inicialização quando o formulário estiver pronto.
    }

    $("#hyp-copy").addEventListener("click", async () => {
      const scenario = parentScenario();

      if (!scenario || !profileWindow) {
        status.textContent = (
          "Complete os dados na Calculadora antes de copiá-los."
        );
        return;
      }

      try {
        await profileWindow.loadScenario(scenario);
        status.textContent = "Dados da Calculadora copiados para este painel.";
        scheduleAll();
      } catch {
        status.textContent = "Não foi possível copiar os dados.";
      }
    });

    let lastHeight = 0;

    new ResizeObserver(() => {
      const height = Math.ceil(document.body.scrollHeight + 30);

      if (Math.abs(height - lastHeight) < 5) return;
      lastHeight = height;

      if (window.parent !== window) {
        window.parent.postMessage(
          {type: "hypothesis:height", height},
          window.location.origin
        );
      }
    }).observe(document.body);
  }

  if ($("#hypothesis-app")) {
    installPage();
  } else if (window.top === window) {
    installTab();
  }
})();
"""
