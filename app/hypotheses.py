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
from fastapi.responses import RedirectResponse
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


@router.get("/api/hypotheses/level-vi")
def level_vi_table():
    return [
        {
            "grade": grade,
            "salary": salary,
            "points": int(points),
            "variable_points": int(points) // 2,
        }
        for grade, salary, points in LEVEL_VI
    ]


@router.get("/hypotheses")
def hypotheses_page():
    # A antiga página avulsa agora é uma aba da aplicação principal.
    return RedirectResponse("/#hypotheses")
