import json
from datetime import date
from decimal import Decimal as D
import pytest
from app.database import store_parameters, resolve_parameters, create_db
from app.schemas import Parameters


def test_home_health_and_functional_request(client):
    assert client.get('/health').json()=={'status':'ok','database':'connected'}
    page=client.get('/')
    assert page.status_code==200 and 'Áreas da calculadora' in page.text
    assert 'Simular um ato com saldos homologados' not in page.text
    assert 'Pagamento de RRA · anos anteriores' not in page.text
    assert 'Entenda sua remuneração' not in page.text
    assert 'value="no_institutional" selected' in page.text
    assert "script-src 'self'" in page.headers['content-security-policy']
    response=client.post('/api/calculate',json={})
    assert response.status_code==200
    result=response.json()
    assert result['monthly']['net']=='5889.55'
    assert isinstance(result['monthly']['gross'],str)
    assert len(result['monthly']['pension']['bands'])==5
    assert result['annual']['thirteenth']['income_tax']['amount']=='980.55'


def test_invalid_api_requests_and_missing_parameters(client):
    for payload in [{'adi':101},{'mode':'official','competence':'2027-01'},{'competence':'2027-01'},{'level':'VI'},{'competence':'2026-13'},{'unknown':'field'}]:
        assert client.post('/api/calculate',json=payload).status_code==422
    assert client.get('/api/parameters?competence=garbage').status_code==422
    assert client.get('/api/parameters?mode=invalid').status_code==422
    assert client.post('/api/calculate',content=b'x'*(1024*1024+1)).status_code==413


def test_comparison_and_commission_options(client):
    r=client.post('/api/commission-options',json={'commission':'COMISSÃO DEMO'}).json()
    assert len(r['results'])==3
    assert r['best_monthly']==2
    assert r['best_annual']==2
    assert r['results'][0]['difference']['monthly']=='0.00'
    assert client.post('/api/compare',json={'scenarios':[{},{}]}).status_code==200
    assert client.post('/api/compare',json={'scenarios':[{}]*4}).status_code==422
    assert client.post('/api/compare',json={'scenarios':[{}, {'competence':'2026-11'}]}).status_code==422


def test_export_reusable_memory_and_csv_injection(client):
    payload={'rubrics':[{'name':'=HYPERLINK("example")','amount':'1','source':'+unsafe'}]}
    exported=client.post('/api/export/json',json=payload)
    assert exported.status_code==200
    memory=exported.json()
    repeated=client.post('/api/calculate',json=memory['scenario']).json()
    assert memory==repeated
    csv=client.post('/api/export/csv',json=payload)
    assert csv.status_code==200
    assert "'=HYPERLINK" in csv.text
    assert "'+unsafe" in csv.text
    assert '5889.55' not in csv.text # acrescentou uma rubrica de R$1
    assert client.post('/api/export/xml',json={}).status_code==404


def test_version_immutable_import_and_official_resolution(client,parameters):
    sessions=client.app.state.sessions
    p=parameters.model_copy(deep=True)
    p.version='audit-test'
    p.status='verified'
    p.verified_at=date(2026,10,23)
    p.valid_from=date(2027,1,1);p.valid_until=date(2027,12,31);p.effective_competence='2027-01'
    with sessions() as s:
        store_parameters(s,p)
        store_parameters(s,p)
        assert resolve_parameters(s,'2027-10','official').version=='audit-test'
        modified=p.model_copy(deep=True)
        modified.positions[0].salary=D('123')
        with pytest.raises(ValueError,match='diferente'):store_parameters(s,modified)
        overlap=p.model_copy(update={'version':'overlap'})
        with pytest.raises(ValueError,match='sobrepostas'):store_parameters(s,overlap)
    assert client.post('/api/calculate',json={'mode':'official'}).status_code==200


def test_schema_validation_of_parameters(parameters):
    p=parameters.model_dump(mode='json')
    p['positions'].append(p['positions'][0])
    with pytest.raises(ValueError,match='duplicada'):Parameters.model_validate(p)
    p=parameters.model_dump(mode='json')
    p['pension_bands'][0]['upper']=None
    with pytest.raises(ValueError):Parameters.model_validate(p)
    p=parameters.model_dump(mode='json')
    p['status']='verified'
    with pytest.raises(ValueError,match='verified_at'):Parameters.model_validate(p)


def test_postgres_url_security_and_driver():
    e,_=create_db('postgresql://user:password@host/database')
    assert e.url.drivername=='postgresql+psycopg'
    assert e.url.query['sslmode']=='require'
    with pytest.raises(ValueError,match='sslmode'):
        create_db('postgresql://user:password@host/database?sslmode=disable')
    e.dispose()


def test_sources_catalog(client):
    r=client.get('/api/sources').json()
    assert len(r['attachments'])==11
    assert all(len(a['sha256'])==64 for a in r['attachments'])
    assert r['versions'][0]['status']=='demo'
    import hashlib
    from pathlib import Path
    directory=Path(__file__).parents[1]/'docs/legislacao'
    for attachment in r['attachments']:
        assert hashlib.sha256((directory/attachment['file']).read_bytes()).hexdigest()==attachment['sha256']


def test_historical_transcription_is_separate_from_calculation(client):
    reference=client.get('/api/historical-reference').json()
    assert reference['status']=='historical_reference_only'
    assert len(reference['positions'])==50
    assert reference['positions'][0]=={'level':'I','grade':'A','historical_salary':'1760.00','historical_gdpi_points':600}
    assert reference['positions'][-1]['historical_gdpi_points']==2870
    assert client.get('/api/parameters').json()['positions'][0]['salary']=='4000'
    assert client.post('/api/calculate',json={'competence':'2010-10'}).status_code==422


def test_future_career_and_retroactive(client):
    r=client.post('/api/career',json={'scenario':{},'future_level':'II','future_grade':'A','years':5})
    assert r.status_code==200
    r=r.json()
    assert len(r['series'])==5
    assert D(r['series'][-1]['accumulated_difference'])==5*D(r['annual_difference'])
    r=client.post('/api/retroactive',json={'entries':[[{'competence':'2026-01'},{'competence':'2026-01','grade':'B'}],[{'competence':'2026-02'},{'competence':'2026-02','grade':'B'}]]})
    assert r.status_code==200
    result=r.json()
    assert D(result['total_net_difference'])==sum(D(x['net_difference']) for x in result['entries'])
    assert 'RRA' in result['warning']
    assert client.post('/api/retroactive',json={'entries':[[{}, {'competence':'2026-01'}]]}).status_code==422


def act_payload(**changes):
    return {'scenario':{},'requirement_date':'2026-10-01','protocol_date':'2026-10-02',
            'level_start':'2020-10-01','probation_complete':True,'satisfactory':True,
            'progression_balance':'20','promotion_balance':'50',**changes}


def test_promotion_precedes_progression_and_balances_stay_separate(client):
    r=client.post('/api/career/act',json=act_payload()).json()
    assert r['act']=='promotion'
    assert r['target']=={'level':'II','grade':'A'}
    assert r['progression_balance']=='20'
    assert r['promotion_balance']=='0'
    assert r['publication_date'] is None and r['financial_date'] is None


def test_progression_limits_and_unmet_interstice(client):
    r=client.post('/api/career/act',json=act_payload(level_start='2025-01-01',prior_progressions_this_year=3)).json()
    assert r['act']=='progression' and r['target']['grade']=='B'
    assert r['progression_balance']=='15'
    assert r['promotion_balance']=='50'
    for changes in [{'satisfactory':False},{'probation_complete':False},{'blocked_until':'2026-12-31'}, {'protocol_date':'2026-09-01'}, {'financial_date':'2026-11-01'}]:
        assert client.post('/api/career/act',json=act_payload(**changes)).status_code==422


def test_public_sources_catalog_covers_career_and_payroll(client):
    from urllib.parse import urlparse
    catalog=client.get('/api/sources').json()['catalog']
    items=[item for group in catalog['sections'] for item in group['items']]
    titles={item['title'] for item in items}
    assert {'Lei nº 18.974/2010','Lei nº 15.961/2005','Lei nº 13.085/1998',
            'Lei nº 20.336/2012','Lei nº 21.334/2014','Decreto nº 45.600/2011',
            'Decreto nº 46.030/2012','Decreto nº 46.640/2014','Decreto nº 46.956/2016',
            'Decreto nº 47.081/2016','Instrução Normativa SEPLAG nº 001/2018',
            'Lei Complementar nº 64/2002','Lei nº 25.143/2025',
            'Lei federal nº 15.270/2025','Instrução Normativa RFB nº 1.500/2014'}<=titles
    assert len(titles)==len(items)
    for item in items:
        parsed=urlparse(item['url'])
        assert parsed.scheme=='https' and (parsed.hostname.endswith('.gov.br') or parsed.hostname.endswith('.jus.br'))
        assert len(item['description'])>30


def test_hypotheses_page_and_assets(client):
    page=client.get('/hypotheses')
    assert page.status_code==200
    assert '<td>J</td><td>R$ 16.378,63</td><td>3410</td><td>1705</td>' in page.text
    assert '/static/hypotheses.js' in page.text and '/static/hypotheses.css' in page.text
    assert '/static/hypotheses.js' in client.get('/').text
    for asset in ('hypotheses.js','hypotheses.css','app.js','style.css'):
        assert client.get('/static/'+asset).status_code==200
