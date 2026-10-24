"""Neon/PostgreSQL em produção; SQLite para desenvolvimento sem credenciais."""
import os
from pathlib import Path
from sqlalchemy import JSON, String, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.engine import make_url
from .schemas import Parameters, CareerData


class Base(DeclarativeBase):
    pass


class ParameterSet(Base):
    __tablename__ = 'parameter_sets'
    version: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class CareerDataSet(Base):
    __tablename__ = 'career_data_sets'
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
    for version in p.supersedes:
        row=session.get(ParameterSet,version)
        if row is None:
            raise ValueError('Versão substituída deve existir no histórico.')
        prior=Parameters.model_validate(row.payload)
        if prior.status!=p.status or not (p.valid_from<=prior.valid_from and p.valid_until>=prior.valid_until):
            raise ValueError('Substituição exige mesmo status e cobertura integral da vigência anterior.')
    if p.status != 'demo':
        for row in session.scalars(select(ParameterSet)):
            other = Parameters.model_validate(row.payload)
            if other.status == p.status and p.valid_from <= other.valid_until and other.valid_from <= p.valid_until:
                if other.version in p.supersedes and p.valid_from<=other.valid_from and p.valid_until>=other.valid_until:
                    continue
                raise ValueError('Vigências sobrepostas no mesmo status; divida os intervalos explicitamente.')
    if p.version in p.supersedes:
        raise ValueError('Uma versão não pode substituir a si própria.')
    session.add(ParameterSet(version=p.version, payload=payload))
    session.commit()


def initialize(engine, sessions):
    Base.metadata.create_all(engine)
    with sessions() as session:
        p = Parameters.model_validate_json((Path(__file__).parent.parent / 'data/demo.json').read_text())
        store_parameters(session, p)
        career=CareerData.model_validate_json((Path(__file__).parent.parent / 'data/career-2026.json').read_text())
        store_career_data(session,career)
        for filename in ('payroll-2026.json','payroll-2026-v2.json','payroll-2026-v3.json'):
            seed_payroll(session,Path(__file__).parent.parent/'data'/filename)


def seed_payroll(session,path):
    payroll=Parameters.model_validate_json(path.read_text())
    # Preservar versões administrativas; somente sucessoras explícitas se sobrepõem.
    if session.get(ParameterSet,payroll.version):
        store_parameters(session,payroll)
    else:
        existing=[Parameters.model_validate(row.payload) for row in session.scalars(select(ParameterSet))]
        overlap=any(p.status=='verified' and p.version not in payroll.supersedes and payroll.valid_from<=p.valid_until and p.valid_from<=payroll.valid_until for p in existing)
        if not overlap:
            store_parameters(session,payroll)


def store_career_data(session, p):
    current=session.get(CareerDataSet,p.version)
    payload=p.model_dump(mode='json')
    if current:
        if CareerData.model_validate(current.payload).model_dump(mode='json') != payload:
            raise ValueError('Versão remuneratória existente com conteúdo diferente; crie outra versão.')
        return
    for row in session.scalars(select(CareerDataSet)):
        other=CareerData.model_validate(row.payload)
        if p.valid_from <= other.valid_until and other.valid_from <= p.valid_until:
            raise ValueError('Tabelas remuneratórias reais com vigências sobrepostas.')
    session.add(CareerDataSet(version=p.version,payload=payload))
    session.commit()


def resolve_parameters(session, competence, mode):
    from datetime import date
    from .calculator import CalculationError
    day = date.fromisoformat(competence + '-01')
    if mode == 'real':
        payroll=[Parameters.model_validate(row.payload) for row in session.scalars(select(ParameterSet))]
        payroll=[p for p in payroll if p.status=='verified' and p.valid_from<=day<=p.valid_until]
        replaced={v for p in payroll for v in p.supersedes}
        payroll=[p for p in payroll if p.version not in replaced]
        if len(payroll)>1:
            raise CalculationError('Mais de uma versão de folha vigente; resolva a sobreposição dos parâmetros.')
        if payroll:
            return payroll[0]
        valid=[CareerData.model_validate(row.payload) for row in session.scalars(select(CareerDataSet))]
        valid=[p for p in valid if p.valid_from <= day <= p.valid_until]
        if len(valid)!=1:
            raise CalculationError('Nenhuma tabela remuneratória real única cadastrada para a competência.')
        return valid[0]
    valid = [Parameters.model_validate(r.payload) for r in session.scalars(select(ParameterSet))]
    valid = [p for p in valid if p.valid_from <= day <= p.valid_until
             and (p.status == 'demo' if mode == 'demo' else p.status == 'verified')]
    replaced={v for p in valid for v in p.supersedes}
    valid=[p for p in valid if p.version not in replaced]
    if not valid:
        raise CalculationError('Nenhuma tabela ' + ('demonstrativa' if mode == 'demo' else 'oficial auditada') + ' cadastrada para esta competência. Consulte Parâmetros e fontes.')
    if len(valid) != 1:
        raise CalculationError('Mais de um conjunto vigente: resolva a sobreposição de parâmetros.')
    return valid[0]


def database_health(engine):
    with engine.connect() as c:
        c.execute(text('SELECT 1'))
