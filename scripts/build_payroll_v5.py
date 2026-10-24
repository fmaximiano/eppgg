"""Preserva a v4 e calcula o ADE pelo índice de desempenho da Seplag."""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.schemas import Parameters

FAQ = 'data/sources/seplag-ade-perguntas-respostas.pdf'


def build():
    data = json.loads((ROOT / 'data/payroll-2026-v4.json').read_text())
    data['supersedes'] = [*data['supersedes'], data['version']]
    data['version'] = 'eppgg-folha-real-2026-v5'
    data['personal_additions_rules'].update(
        ade_method='performance_index',
        ade_individual_weight='0.7',
        ade_institutional_weight='0.3',
        ade_institutional_score='70',
        ade_min_individual='70',
    )
    data['sources']['ade'] = (
        'Lei 14.693/2003, art. 2º-A; Decreto 44.503/2007 e alterações; Seplag, "ADE · perguntas e respostas", '
        'itens 5, 11, 13, 15 e 18. Índice ADE = P × (0,3 × AI + 0,7 × ADI); valor = VB × índice. P é a faixa '
        'máxima pelo número de avaliações satisfatórias; AI 70 para órgão sem Acordo de Resultados; ADI da última '
        'avaliação concluída até a atualização de 1º de outubro; ADI inferior a 70 não gera ADE no exercício. '
        'Não homologa direito nem resultado de avaliação.'
    )
    data['notes'] = [n for n in data['notes'] if not n.startswith('ADE por número de avaliações')]
    data['notes'].append(
        'ADE pelo índice de desempenho: faixa máxima por número de avaliações satisfatórias (informado ou estimado pelo '
        'ano de ingresso) × (0,3 × AI + 0,7 × ADI). A ADI do ADE é informada separadamente, porque a atualização anual '
        'ocorre em outubro e pode não coincidir com a ADI vigente na GDPI; sem ela, usa-se a ADI da GDPI. AI fixada em '
        '70, hipótese de órgão sem Acordo de Resultados. Percentuais informados em cenários anteriores permanecem '
        'preservados. Bases específicas são mensais integrais; não se atualizam automaticamente com a posição na carreira.'
    )
    data['evidence'].append({
        'component': 'ade_formula',
        'title': 'Seplag · ADE, perguntas e respostas (cópia publicada pelo Sindppen-MG)',
        'url': 'https://sindppenmg.com.br/wp-content/uploads/2022/01/CARTILHA-DE-ADE.pdf',
        'path': FAQ,
        'sha256': hashlib.sha256((ROOT / FAQ).read_bytes()).hexdigest(),
        'checked_at': '2026-10-24',
    })
    p = Parameters.model_validate(data)
    (ROOT / 'data/payroll-2026-v5.json').write_text(p.model_dump_json(indent=2) + '\n')
    print('Gerado:', p.version)


if __name__ == '__main__':
    build()
