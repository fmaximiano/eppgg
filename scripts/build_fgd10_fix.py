"""Corrige a FGD-10 (R$2.072,24 → R$1.966,07) em novas versões, preservando as anteriores."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.schemas import CareerData, Parameters

OLD, NEW = '2072.24', '1966.07'
NOTE = ('FGD-10 corrigida de R$2.072,24 para R$1.966,07: o valor da tabela SEPLAG de 2026 está incorreto '
        '(conferência manual em 2026-10-27).')


def fix(data, version):
    row = next(f for f in data['functions'] if f['code'] == 'FGD-10')
    assert row['amount'] == OLD
    row['amount'] = NEW
    data['supersedes'] = [*data.get('supersedes', []), data['version']]
    data['version'] = version
    data['notes'].append(NOTE)
    return data


def build():
    career = fix(json.loads((ROOT / 'data/career-2026.json').read_text()), 'eppgg-remuneracao-real-2026-v2')
    c = CareerData.model_validate(career)
    (ROOT / 'data/career-2026-v2.json').write_text(json.dumps(c.model_dump(mode='json'), ensure_ascii=False, indent=2) + '\n')
    payroll = fix(json.loads((ROOT / 'data/payroll-2026-v6.json').read_text()), 'eppgg-folha-real-2026-v7')
    p = Parameters.model_validate(payroll)
    (ROOT / 'data/payroll-2026-v7.json').write_text(p.model_dump_json(indent=2) + '\n')
    print('Gerados:', c.version, p.version)


if __name__ == '__main__':
    build()
