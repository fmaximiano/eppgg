import csv
import io
import json
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from .calculator import CalculationError, calculate, money
from .career import project, simulate_act
from .database import create_db, initialize, database_health, resolve_parameters, ParameterSet, CareerDataSet
from .schemas import Scenario, CompareRequest, RetroRequest, CareerRequest, CareerActRequest, Parameters, CareerData
from .schemas import RRARequest, MultipleEmploymentsRequest
from .special_payroll import calculate_rra, consolidate_employments

ROOT = Path(__file__).parent


def encoded(value):
    return jsonable_encoder(value, custom_encoder={Decimal: lambda d: format(d, 'f')})


def create_app(database_url=None):
    engine, sessions = create_db(database_url)

    @asynccontextmanager
    async def lifespan(app):
        initialize(engine, sessions)
        yield
        engine.dispose()

    app = FastAPI(title='Calculadora EPPGG · Minas Gerais', version='0.1.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.sessions = sessions
    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    templates = Jinja2Templates(directory=ROOT / 'templates')

    @app.middleware('http')
    async def headers_and_limit(request: Request, call_next):
        # Limite efetivo também para transferências chunked, antes da desserialização.
        if request.method in ('POST', 'PUT', 'PATCH'):
            total = 0
            chunks = []
            async for chunk in request.stream():
                total += len(chunk)
                if total > 1024 * 1024:
                    return JSONResponse({'detail': 'Requisição excede 1 MB.'}, status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(CalculationError)
    async def calculation_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    def run(s):
        with sessions() as session:
            return calculate(s, resolve_parameters(session, s.competence, s.mode))

    @app.get('/', response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request=request, name='index.html')

    @app.get('/health')
    def health():
        try:
            database_health(engine)
        except Exception:
            return JSONResponse({'status': 'unavailable', 'database': 'unavailable'}, status_code=503)
        return {'status': 'ok', 'database': 'connected'}

    @app.get('/api/parameters')
    def parameters(competence: str = '2026-10', mode: str = 'demo'):
        # Reutiliza validação de competência e de modo, evitando coerção silenciosa.
        try:
            s = Scenario(competence=competence, mode=mode)
        except ValueError:
            raise HTTPException(422, 'Competência ou modo inválido.')
        with sessions() as session:
            return encoded(resolve_parameters(session, s.competence, s.mode).model_dump())

    @app.get('/api/sources')
    def sources():
        with sessions() as session:
            versions = [{k: r.payload.get(k) for k in ('version', 'status', 'valid_from', 'valid_until', 'source', 'verified_at', 'notes','evidence','pension_revaluation','pending','supersedes')}
                        for r in [*session.scalars(select(ParameterSet)),*session.scalars(select(CareerDataSet))]]
        return {'versions': versions, 'attachments': json.loads((ROOT.parent / 'data/legal-sources.json').read_text()),
                'pending': ['Confronto das faixas RPPS reconstruídas com tabela estadual/contracheque',
                            'Regimes externos ao RPPS estadual, aposentados e isenções não cadastradas',
                            'Conferência dos atos de acumulação e documentos do pagamento RRA'],
                'historical_findings': ['Decreto 46.640/2014: F=0,0005 em 2015, 0,0006 em 2016 e 0,0007 desde 2017; não retroagir o fator atual.',
                                        'Decreto 46.956/2016: P remete ao Anexo V da Lei 13.085/1998, respeitado o §6º do art.16.',
                                        'Decreto 47.081/2016: revogou §7º do art.9º do Decreto 46.030/2012; não aplicar a vedação antiga de curso integral.',
                                        'Instrução 001/2018: saldos separados; promoção precede progressão; enquadramento no primeiro grau do novo nível com vencimento superior.']}

    @app.get('/api/career-data')
    def career_data(competence: str = '2026-10'):
        try:
            s=Scenario(competence=competence,mode='real')
        except ValueError:
            raise HTTPException(422,'Competência inválida.')
        from datetime import date
        day=date.fromisoformat(s.competence+'-01')
        with sessions() as session:
            catalogs=[CareerData.model_validate(row.payload) for row in session.scalars(select(CareerDataSet))]
            catalogs=[p for p in catalogs if p.valid_from<=day<=p.valid_until]
            if len(catalogs)!=1:
                raise CalculationError('Nenhum catálogo remuneratório real único para a competência.')
            result=catalogs[0].model_dump()
            payroll=resolve_parameters(session,s.competence,'real')
            result['payroll_available']=isinstance(payroll,Parameters)
            result['payroll_version']=payroll.version if result['payroll_available'] else None
            return encoded(result)

    @app.get('/api/historical-reference')
    def historical_reference():
        return json.loads((ROOT.parent / 'data/historical-reference.json').read_text())

    @app.post('/api/calculate')
    def calc(s: Scenario):
        return encoded(run(s))

    @app.post('/api/compare')
    def compare(body: CompareRequest):
        if len({s.competence for s in body.scenarios}) != 1 or len({s.mode for s in body.scenarios}) != 1:
            raise CalculationError('Compare cenários da mesma competência e modo.')
        results = [run(s) for s in body.scenarios]
        first = results[0]['monthly']['net']
        first_annual = results[0]['annual']['net'] if results[0]['annual'] else None
        for r in results:
            delta = money(r['monthly']['net'] - first) if first is not None and r['monthly']['net'] is not None else None
            annual_delta = money(r['annual']['net'] - first_annual) if first_annual is not None and r['annual'] and r['annual']['net'] is not None else None
            gross_delta=money(r['monthly']['gross']-results[0]['monthly']['gross'])
            r['difference'] = {'monthly': delta, 'monthly_percent': money(delta / abs(first) * 100) if first else None,
                               'annual': annual_delta, 'annual_percent': money(annual_delta / abs(first_annual) * 100) if first_annual and annual_delta is not None else None,
                               'gross':gross_delta,'gross_percent':money(gross_delta/abs(results[0]['monthly']['gross'])*100) if results[0]['monthly']['gross'] else None}
        all_monthly=all(r['monthly']['net'] is not None for r in results)
        all_annual = all(r['annual'] and r['annual']['net'] is not None for r in results)
        return encoded({'results': results, 'best_monthly': max(range(len(results)), key=lambda i: results[i]['monthly']['net']) if all_monthly else None,
                        'best_annual': max(range(len(results)), key=lambda i: results[i]['annual']['net']) if all_annual else None,
                        'best_gross':max(range(len(results)),key=lambda i:results[i]['monthly']['gross'])})

    @app.post('/api/commission-options')
    def commission_options(s: Scenario):
        with sessions() as session:
            p = resolve_parameters(session, s.competence, s.mode)
        commission = next((c for c in p.commissions if c.code == s.commission), None)
        if commission is None:
            raise CalculationError('Selecione um cargo comissionado cadastrado.')
        function=next((f for f in p.functions if f.code==s.function),None)
        baseline={'name':'Sem comissão','remuneration_option':'none','commission_pension':False}
        if function and function.requires_commission_kind:
            baseline.update(function=None,function_pension=False)
        variants = [s.model_copy(update=baseline)]
        for option in ('a', 'b'):
            if getattr(commission, 'allow_' + option):
                variants.append(s.model_copy(update={'name': 'Opção ' + option.upper(), 'remuneration_option': option}))
        return compare(CompareRequest(scenarios=variants))

    @app.post('/api/career')
    def career(r: CareerRequest):
        with sessions() as session:
            p = resolve_parameters(session, r.scenario.competence, r.scenario.mode)
        return encoded(project(r, p))

    @app.post('/api/career/act')
    def career_act(r: CareerActRequest):
        with sessions() as session:
            p = resolve_parameters(session, r.scenario.competence, r.scenario.mode)
        return encoded(simulate_act(r, p))

    @app.post('/api/retroactive')
    def retroactive(r: RetroRequest):
        rows = []
        for before, after in r.entries:
            if before.competence != after.competence or before.mode != after.mode:
                raise CalculationError('Cada par deve ter a mesma competência e modo.')
            a, b = run(before), run(after)
            net_difference=money(b['monthly']['net']-a['monthly']['net']) if a['monthly']['net'] is not None and b['monthly']['net'] is not None else None
            rows.append({'competence': before.competence, 'before': a, 'after': b,
                         'gross_difference': money(b['monthly']['gross'] - a['monthly']['gross']),
                         'net_difference': net_difference})
        return encoded({'entries': rows, 'total_net_difference': money(sum((x['net_difference'] for x in rows), Decimal('0'))) if all(x['net_difference'] is not None for x in rows) else None,
                        'total_gross_difference':money(sum((x['gross_difference'] for x in rows),Decimal('0'))),
                        'warning': 'Diferenças estimadas nas competências de origem. Não calcula IR de RRA, juros, atualização ou líquido da folha de pagamento retroativo.'})

    @app.post('/api/rra')
    def rra(r: RRARequest):
        with sessions() as session:
            p=resolve_parameters(session,r.payment_competence,r.mode)
        return encoded(calculate_rra(r,p))

    @app.post('/api/multiple-employments')
    def multiple_employments(r: MultipleEmploymentsRequest):
        s=r.employments[0].scenario
        with sessions() as session:
            p=resolve_parameters(session,s.competence,s.mode)
        return encoded(consolidate_employments(r,p))

    @app.post('/api/export/{kind}')
    def export(kind: str, s: Scenario):
        result = run(s)
        if kind == 'json':
            return Response(json.dumps(encoded(result), ensure_ascii=False, indent=2), media_type='application/json',
                            headers={'Content-Disposition': 'attachment; filename="memoria-eppgg.json"'})
        if kind != 'csv':
            raise HTTPException(404, 'Formato não disponível.')
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value

        writer.writerow(['Competência', 'Versão', 'Status', 'Rubrica', 'Valor', 'IR', 'RPPS', 'IPSEMG', 'Fonte'])
        for row in result['monthly']['earnings']:
            writer.writerow([s.competence, result['parameters']['version'], result['parameters']['status'], safe(row['name']),
                             format(row['amount'], '.2f'),
                             row['tax'] if result['monthly']['net'] is not None else 'não apurado',
                             row['pension'] if result['monthly']['net'] is not None else 'não apurado',
                             row['health'] if result['monthly']['net'] is not None else 'não apurado',safe(row['source'])])
        m = result['monthly']
        if m['net'] is None:
            writer.writerow([s.competence,result['parameters']['version'],result['parameters']['status'],'Bruto',format(m['gross'],'.2f')])
            writer.writerow([s.competence,result['parameters']['version'],result['parameters']['status'],'Descontos e líquido não apurados; consultar pendências'])
            return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',
                            headers={'Content-Disposition':'attachment; filename="remuneracao-real-eppgg.csv"'})
        for name, amount, key in [('RPPS', m['pension']['amount'], 'pension'), ('Complementar', m['complementary'], 'pension'),
                                  ('IPSEMG', m['health']['amount'], 'health'), ('Coparticipação', m['health']['copay'], 'health'),
                                  ('IRRF', m['income_tax']['amount'], 'tax'), ('Pensão alimentícia', m['alimony'], 'tax'),
                                  ('Outros descontos', m['other_deductions'], 'tax')]:
            writer.writerow([s.competence, result['parameters']['version'], result['parameters']['status'], name,
                             format(-amount, '.2f'), '', '', '', safe(result['parameters']['sources'][key])])
        writer.writerow([s.competence, result['parameters']['version'], result['parameters']['status'], 'Líquido', format(m['net'], '.2f')])
        return Response('\ufeff' + output.getvalue(), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="demonstrativo-eppgg.csv"'})

    return app


app = create_app()
