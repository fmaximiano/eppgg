"""Integração opcional em banco PostgreSQL de TESTE, com TLS.

TEST_DATABASE_URL deve apontar para banco descartável (não produção).
"""
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.database import create_db, store_parameters, ParameterSet
from app.schemas import Parameters


def main():
    url=os.environ['TEST_DATABASE_URL']
    app=create_app(url)
    version='test-'+uuid4().hex
    engine,sessions=create_db(url)
    try:
        with TestClient(app) as client:
            assert client.get('/health').status_code==200
            result=client.post('/api/calculate',json={})
            assert result.status_code==200
            assert result.json()['monthly']['net']=='5889.55'
            p=Parameters.model_validate_json((Path(__file__).parents[1]/'data/demo.json').read_text())
            p.version=version;p.status='verified';p.verified_at=date(2026,10,23)
            with sessions() as session:
                store_parameters(session,p)
                store_parameters(session,p)
        # Nova instância do app usa a versão persistida, sem depender de estado em memória.
        with TestClient(create_app(url)) as client:
            result=client.post('/api/calculate',json={'mode':'official'})
            assert result.status_code==200
            assert result.json()['parameters']['version']==version
            assert result.json()['monthly']['net']=='5889.55'
        with engine.connect() as connection:
            from sqlalchemy import text
            assert connection.execute(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')).scalar() is True
        print('PASS: PostgreSQL com TLS, schema, importação idempotente, persistência entre instâncias e cálculo funcional.')
    finally:
        with sessions() as session:
            row=session.get(ParameterSet,version)
            if row:
                session.delete(row);session.commit()
        engine.dispose()


if __name__=='__main__':main()
