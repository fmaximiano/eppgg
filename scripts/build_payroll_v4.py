"""Preserva o histórico e habilita a estimativa do ADE por avaliações satisfatórias."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.schemas import Parameters


def build():
    data = json.loads((ROOT / 'data/payroll-2026-v3.json').read_text())
    data['supersedes'] = [*data['supersedes'], data['version']]
    data['version'] = 'eppgg-folha-real-2026-v4'
    data['personal_additions_rules']['ade_method'] = 'satisfactory_evaluations'
    data['sources']['ade'] = 'Lei 14.693/2003; Decreto 44.503/2007 e alterações; orientação Seplag sobre ADE. Estimativa pela faixa correspondente à quantidade de avaliações, considerando avaliações satisfatórias e aproveitamento integral da faixa. Ano de ingresso: ano da competência menos ano de ingresso. Não homologa direito nem resultado de avaliação.'
    data['notes'] = [n for n in data['notes'] if not n.startswith('Quinquênios e ADE dependem')]
    data['notes'].append('ADE por número de avaliações satisfatórias ou ano de ingresso, com aproveitamento integral da faixa. A estimativa por ano considera uma avaliação satisfatória por ano completo transcorrido, sem inferir a data exata de conclusão do probatório ou afastamentos. Percentuais informados em cenários anteriores permanecem preservados. Bases específicas são mensais integrais; não se atualizam automaticamente com a posição na carreira.')
    data['pending'] = [n for n in data['pending'] if not n.startswith('Determinação automática do percentual anual')]
    data['pending'].append('Conferência de avaliações efetivas, calendário de concessão do ADE e composição histórica das bases pessoais com o ato do vínculo.')
    p = Parameters.model_validate(data)
    (ROOT / 'data/payroll-2026-v4.json').write_text(p.model_dump_json(indent=2) + '\n')
    print('Gerado:', p.version)


if __name__ == '__main__':
    build()
