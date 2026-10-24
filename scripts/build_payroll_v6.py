"""Preserva a v5 e calcula o ADE só pela ADI, sem avaliação institucional."""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.schemas import Parameters

DECREE = 'data/sources/decreto-44503-consolidado-2014.pdf'


def build():
    data = json.loads((ROOT / 'data/payroll-2026-v5.json').read_text())
    data['supersedes'] = [*data['supersedes'], data['version']]
    data['version'] = 'eppgg-folha-real-2026-v6'
    rules = data['personal_additions_rules']
    rules['ade_method'] = 'individual_index'
    for key in ('ade_individual_weight', 'ade_institutional_weight', 'ade_institutional_score'):
        rules[key] = None
    data['sources']['ade'] = (
        'Lei 14.693/2003, art. 2º-A; Decreto 44.503/2007, art. 4º e Anexo II: ADE = P × VB × (0,3 × AI + 0,7 × ADI). '
        'Sem Avaliação de Desempenho Institucional (Acordo de Resultados extinto), o art. 4º, § 8º, na redação do '
        'Decreto 46.756/2015, manda considerar integralmente o resultado da ADI: ADE = P × VB × ADI. '
        'https://www.almg.gov.br/legislacao-mineira/texto/DEC/46756/2015/ '
        'P é a faixa máxima pelo número de avaliações satisfatórias; ADI da última avaliação concluída até a '
        'atualização de 1º de outubro; ADI inferior a 70 não gera ADE no exercício. Não homologa direito nem resultado de avaliação.'
    )
    data['notes'] = [n for n in data['notes'] if not n.startswith('ADE pelo índice de desempenho')]
    data['notes'].append(
        'ADE = faixa máxima por número de avaliações satisfatórias (informado ou estimado pelo ano de ingresso) × ADI. '
        'Sem avaliação institucional, a ADI é considerada integralmente (Decreto 46.756/2015), em substituição à nota '
        '70 atribuída à parcela institucional na redação de 2012 usada pela v5. A ADI do ADE é informada separadamente, '
        'porque a atualização anual ocorre em outubro; sem ela, usa-se a ADI da GDPI. Percentuais informados em cenários '
        'anteriores permanecem preservados. Bases específicas são mensais integrais.'
    )
    data['pending'].append(
        'Arquivar cópia do Decreto 46.756/2015: o portal da ALMG não pôde ser baixado na geração da v6; '
        'o texto foi conferido na consulta pública e está referenciado por URL.'
    )
    data['evidence'].append({
        'component': 'ade_decree',
        'title': 'Decreto 44.503/2007 consolidado até 2014 (cópia publicada pela UEMG): art. 4º e Anexo II',
        'url': 'https://www.uemg.br/downloads/Decreto_44503_2007.pdf',
        'path': DECREE,
        'sha256': hashlib.sha256((ROOT / DECREE).read_bytes()).hexdigest(),
        'checked_at': '2026-10-24',
    })
    p = Parameters.model_validate(data)
    (ROOT / 'data/payroll-2026-v6.json').write_text(p.model_dump_json(indent=2) + '\n')
    print('Gerado:', p.version)


if __name__ == '__main__':
    build()
