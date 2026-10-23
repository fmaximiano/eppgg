"""Operações administrativas locais; sem endpoint público para alterar tabelas."""
import argparse
from pathlib import Path
from .database import create_db, initialize, store_parameters
from .schemas import Parameters


def main():
    parser = argparse.ArgumentParser(description='Importar parâmetros auditados no banco configurado por DATABASE_URL.')
    parser.add_argument('command', choices=['init-db', 'import-parameters', 'schema'])
    parser.add_argument('file', nargs='?')
    args = parser.parse_args()
    if args.command == 'schema':
        import json
        print(json.dumps(Parameters.model_json_schema(), ensure_ascii=False, indent=2))
        return
    engine, sessions = create_db()
    initialize(engine, sessions)
    if args.command == 'import-parameters':
        if not args.file:
            parser.error('Informe o arquivo JSON.')
        params = Parameters.model_validate_json(Path(args.file).read_text())
        with sessions() as session:
            store_parameters(session, params)
        print(f'Importado: {params.version} ({params.status})')
    else:
        print('Banco inicializado; remuneração real de 2026 e dados demonstrativos disponíveis.')


if __name__ == '__main__':
    main()
