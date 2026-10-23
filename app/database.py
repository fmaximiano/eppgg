"""Neon/PostgreSQL em produção; SQLite para desenvolvimento sem credenciais."""
import os
from pathlib import Path
from sqlalchemy import JSON, String, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.engine import make_url
from .schemas import Parameters


class Base(DeclarativeBase):
    pass


class ParameterSet(Base):
    __tablename__ = 'parameter_sets'
    version: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


def create_db(url=None):
    url = url or os.getenv('DATABASE_URL', 'sqlite:///./eppgg.db')
    parsed = make_url(url)
    if parsed.drivername in ('postgres', 'postgresql'):
        parsed = parsed.set(drivername='postgresql+psycopg')
    if parsed.get_backend_name() == 'postgresql':
        # Nunca desativar TLS para Neon, incluindo connection strings sem query.
        sslmode = parsed.query.get('sslmode', 'require')
        if sslmode not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError('PostgreSQL exige sslmode=require, verify-ca ou verify-full.')
        parsed = parsed.update_query_dict({'sslmode': sslmode})
    kwargs = {'connect_args': {'check_same_thread': False}} if parsed.get_backend_name() == 'sqlite' else {}
    engine = create_engine(parsed, pool_pre_ping=True, **kwargs)
    return engine, sessionmaker(engine)


def store_parameters(session, p):
    """Versões imutáveis. Reimportar conteúdo idêntico é idempotente."""
    current = session.get(ParameterSet, p.version)
    payload = p.model_dump(mode='json')
    if current:
        if Parameters.model_validate(current.payload).model_dump(mode='json') != payload:
            raise ValueError('Versão existente com conteúdo diferente. Use uma nova versão.')
        return
    if p.status != 'demo':
        for row in session.scalars(select(ParameterSet)):
            other = Parameters.model_validate(row.payload)
            if other.status == p.status and p.valid_from <= other.valid_until and other.valid_from <= p.valid_until:
                raise ValueError('Vigências sobrepostas no mesmo status; divida os intervalos explicitamente.')
    session.add(ParameterSet(version=p.version, payload=payload))
    session.commit()


def initialize(engine, sessions):
    Base.metadata.create_all(engine)
    with sessions() as session:
        p = Parameters.model_validate_json((Path(__file__).parent.parent / 'data/demo.json').read_text())
        store_parameters(session, p)


def resolve_parameters(session, competence, mode):
    from datetime import date
    from .calculator import CalculationError
    day = date.fromisoformat(competence + '-01')
    valid = [Parameters.model_validate(r.payload) for r in session.scalars(select(ParameterSet))]
    valid = [p for p in valid if p.valid_from <= day <= p.valid_until
             and (p.status == 'demo' if mode == 'demo' else p.status == 'verified')]
    if not valid:
        raise CalculationError('Nenhuma tabela ' + ('demonstrativa' if mode == 'demo' else 'oficial auditada') + ' cadastrada para esta competência. Consulte Parâmetros e fontes.')
    if len(valid) != 1:
        raise CalculationError('Mais de um conjunto vigente: resolva a sobreposição de parâmetros.')
    return valid[0]


def database_health(engine):
    with engine.connect() as c:
        c.execute(text('SELECT 1'))
