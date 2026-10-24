"""Sucessora imutável: adicionais pessoais reconhecidos no vínculo."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.schemas import Parameters


def build():
    data = json.loads((ROOT / 'data/payroll-2026-v2.json').read_text())
    data['supersedes'] = [*data['supersedes'], data['version']]
    data['version'] = 'eppgg-folha-real-2026-v3'
    data['verified_at'] = '2026-10-24'
    data['personal_additions_rules'] = {
        'quinquennium_rate': '0.10', 'ade_max_rate': '0.70',
        'ade_method': 'granted_percentage',
        'ade_reference_ceilings': [
            {'evaluations': n, 'rate': r} for n, r in (
                (3, '0.06'), (5, '0.10'), (10, '0.20'), (15, '0.30'),
                (20, '0.40'), (25, '0.50'), (30, '0.60'), (35, '0.70'))
        ],
    }
    data['sources']['quinquennium'] = 'Constituição do Estado de Minas Gerais, ADCT, art.112; EC 57/2003. Quinquênios reconhecidos, de 10% cada, sobre a base aplicável ao vínculo. Composição especial e direito adquirido conforme ato de concessão.'
    data['sources']['ade'] = 'Lei 14.693/2003; Decreto 44.503/2007 e alterações; orientação Seplag sobre ADE. Percentual vigente concedido, até 70%; não é inferido da ADI usada na GDPI.'
    path = 'data/sources/seplag-adicional-desempenho.pdf'
    checksum = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if checksum != '4987706b5947e7e233542482d56cb63fbe1dd2c7fb4565f1640f1fc3e044353e':
        raise ValueError('Orientação da Seplag mudou; revisar antes de gerar parâmetros.')
    data['evidence'].append({
        'component': 'ade', 'title': 'Seplag · Adicional de Desempenho',
        'url': 'https://www.mg.gov.br/system/files/media/planejamento/documento_detalhado/2022/gestao-de-pessoas/direitos-e-deveres-do-servidor/adicional_de_desempenho_ade.pdf',
        'path': path, 'sha256': checksum, 'checked_at': '2026-10-24',
    })
    data['notes'].append('Quinquênios e ADE dependem do enquadramento e dos direitos reconhecidos em cada vínculo. O ADE usa percentual vigente informado, sem transformar as faixas máximas ou a ADI da GDPI em concessão automática. A opção pelo ADE preserva apenas os quinquênios já adquiridos. Bases especiais são informadas em valor mensal integral e recebem a fração do mês uma única vez.')
    data['pending'].append('Determinação automática do percentual anual do ADE e da composição histórica das bases dos adicionais: usar percentual concedido e, quando necessário, base reconhecida no vínculo.')
    p = Parameters.model_validate(data)
    (ROOT / 'data/payroll-2026-v3.json').write_text(p.model_dump_json(indent=2) + '\n')
    print('Gerado:', p.version)


if __name__ == '__main__':
    build()
