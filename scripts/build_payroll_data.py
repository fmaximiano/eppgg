"""Gera o conjunto de folha de 2026 sem ler fixtures demonstrativas.

A atualização RPPS segue LC 64/2002, art.28, §5º. Mantém a memória anual
para revisão e confronta o último limite com o teto RGPS publicado em 2026.
Uso: .venv/bin/python scripts/build_payroll_data.py /workspace/official-research
"""
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
# Publicações consultadas, preservadas integralmente para conferência.
FILES={
 'pension':('21390ff3d282.html','lc-64-consolidada.html','LC 64/2002, arts.26 e 28','https://www.almg.gov.br/legislacao-mineira/texto/LCP/64/2002/?cons=1'),
 'health_law':('d7b54ea697d7.html','lei-25143-ipsemg.html','Lei 25.143/2025, arts.4º e 6º','https://www.almg.gov.br/legislacao-mineira/texto/LEI/25143/2025/?cons=1'),
 'health_regulation':('ea53b3886252.html','decreto-48981-ipsemg.html','Decreto 48.981/2025, arts.4º–5º','https://www.almg.gov.br/legislacao-mineira/texto/DEC/48981/2025/?cons=1'),
 'health_age':('bfb81ffa9a4d.html','ans-faixas-etarias.html','ANS, faixa etária de 59 anos ou mais','https://www.gov.br/ans/pt-br/assuntos/consumidor/reajuste-variacao-de-mensalidade/reajuste-por-mudanca-de-faixa-etaria'),
 'tax':('0c74c393ba58.html','rfb-tributacao-2026.html','Receita Federal, tabelas e redução de 2026','https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2026'),
 'tax_examples':('aa49aa1fbb7a.html','rfb-exemplos-reducao-2026.html','Receita Federal, exemplos da Lei 15.270/2025','https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/exemplos-de-aplicacao-da-lei-15-270-2025'),
 'rgps_2026':('83d4e7c28db3.pdf','portaria-mps-mf-13-2026.pdf','Portaria MPS/MF 13/2026, arts.1º–2º','https://www.gov.br/previdencia/pt-br/assuntos/rpps/documentos/PortariaInterministerialMPSMF13de9dejaneirode2026.pdf'),
 'rgps_table':('9cebad38d2d2.html','inss-tabela-contribuicao-2026.html','INSS, salário mínimo e teto de contribuição 2026','https://www.gov.br/inss/pt-br/direitos-e-deveres/inscricao-e-contribuicao/tabela-de-contribuicao-mensal'),
 'rgps_2021':('0beeba8bf326.pdf','portaria-seprt-636-2021.pdf','Portaria SEPRT 636/2021, art.1º, índice RGPS 5,45%','https://www.gov.br/previdencia/pt-br/assuntos/rpps/legislacao-dos-rpps/portarias/portarias_todas/portaria-seprt-no-636-de-13-de-janeiro-de-2021.pdf'),
 'rgps_2022':('b6feddb5a230.pdf','portaria-mtp-me-12-2022.pdf','Portaria MTP/ME 12/2022, art.1º, índice RGPS 10,16%','https://www.gov.br/previdencia/pt-br/assuntos/rpps/legislacao-dos-rpps/portarias/portarias_todas/portaria-interministerial-mtp-me-no-12-de-17-de-janeiro-de-2022.pdf'),
 'rgps_2023':('f2beccb01cdd.pdf','portaria-mps-mf-26-2023.pdf','Portaria MPS/MF 26/2023, art.1º, índice RGPS 5,93%','https://www.gov.br/previdencia/pt-br/assuntos/rpps/legislacao-dos-rpps/portarias/portarias_todas/portaria-interministerial-mps-mf-no-26-de-10-de-janeiro-de-2023.pdf'),
}
EXPECTED_SHA256={'pension': '3f9bb9de9710162b02d0d3a7f0dcafc75bce7417c9a9167c1d1d5c445bee4426',
 'health_law': 'fe125af523459ac7cef26a9740329c8caa89eabed614bcb753de0cab2236a9f2',
 'health_regulation': '8ffd50d5f3920c4f9dadd3eb8fa6495f669d7a621312a1369ce4a464c4b1fc04',
 'health_age': '1e4464a8b42fcaab06134a126c5d8c5e08b1f0fcda0547d5e952f46c4241da55',
 'tax': '349a6985f704b26d4719f8d526d99b3211b106ea3146f5ca5f62e1f3d992b97e',
 'tax_examples': 'bebfcebdb43de4f3c7c551641ad7140bb010cad4dd4b2c6e20766b77740e68d7',
 'rgps_2026': '94d3a9adda05c9463bde8bf89dba5756fe9885aba92858064062123f51bfd634',
 'rgps_table': '0b7d8ea96f3edf73efcc67726b92111c3d2a5553b5e69e0908a2dda0cf53d7c8',
 'rgps_2021': '75bea0f4873d3eb0b4c4682f4e3757adb15989b6464a39fab49b950a4426365a',
 'rgps_2022': '477df44813fd3f01af37528d28e94f97400a25cac4abb76fa812128fe73908ce',
 'rgps_2023': 'ea4230a2b7713fa621b4fc2ab8ff943d8fc3317f9a2d8e86b15521002cf69a60'}
REVALUATIONS=[(2021,'0.0545','Portaria SEPRT 636/2021, art.1º'),
 (2022,'0.1016','Portaria MTP/ME 12/2022, art.1º'),
 (2023,'0.0593','Portaria MPS/MF 26/2023, art.1º'),
 (2024,'0.0371','Portaria MPS/MF 2/2024, art.1º'),
 (2025,'0.0477','Portaria MPS/MF 6/2025, art.1º'),
 (2026,'0.0390','Portaria MPS/MF 13/2026, art.1º')]

def cent(value):return value.quantize(D('.01'),rounding=ROUND_HALF_UP)

def build(source_dir):
 career=json.loads((ROOT/'data/career-2026.json').read_text())
 evidence=list(career['evidence'])
 for key,(input_name,output_name,title,url) in FILES.items():
  path=source_dir/input_name
  blob=path.read_bytes()
  if hashlib.sha256(blob).hexdigest()!=EXPECTED_SHA256[key]:
   raise ValueError("Fonte mudou; revise explicitamente e crie nova versão: "+input_name)
  if path.suffix=='.pdf' and not blob.startswith(b'%PDF'):
   raise ValueError('Fonte não é PDF: '+input_name)
  if b'credentials_cookie_auth/require_login' in blob and path.suffix=='.html':
   raise ValueError('Fonte exige autenticação: '+input_name)
  (ROOT/'data/sources').mkdir(exist_ok=True)
  shutil.copyfile(path,ROOT/'data/sources'/output_name)
  evidence.append({'component':key,'title':title,'url':url,'path':'data/sources/'+output_name,
                   'sha256':hashlib.sha256(blob).hexdigest(),'checked_at':'2026-10-23'})
 limits=[D(v) for v in ['1500','2500','3500','4500','5500','6101.06']]
 history=[{'year':2020,'index':'0','upper_limits':[str(x) for x in limits],'source':'LC 64/2002, art.28, redação LC 156/2020'}]
 for year,index,source in REVALUATIONS:
  limits=[cent(v*(1+D(index))) for v in limits]
  history.append({'year':year,'index':index,'upper_limits':[str(x) for x in limits],'source':source})
 if limits[-1]!=D('8475.55'):
  raise ValueError('Cadeia de reajustes não confere com o teto RGPS 2026.')
 data={k:career[k] for k in ['positions','commissions','functions','gdpi_factor','gdpi_reference_salary','gdpi_point_share','gdpi_min_adi','gdpi_pension','gdpi_health','career_rules']}
 data.update({'version':'eppgg-folha-real-2026-v1','valid_from':'2026-01-01','valid_until':'2026-12-31',
  'effective_competence':'2026-01','status':'verified','verified_at':'2026-10-23',
  'source':'Parâmetros de remuneração e descontos de 2026, com fontes normativas e memória de atualização. Conferência documental; estimativa, sem homologação de contracheque.',
  'sources':{**career['sources'],
   'pension':'LC 64/2002, arts.26 e 28, especialmente §5º: faixas recompostas anualmente pelos índices RGPS. Ver memória 2020–2026 e Portarias SEPRT 636/2021, MTP/ME 12/2022, MPS/MF 26/2023, 2/2024, 6/2025 e 13/2026. https://www.almg.gov.br/legislacao-mineira/texto/LCP/64/2002/?cons=1',
   'health':'Lei 25.143/2025, arts.4º e 6º; Decreto 48.981/2025, arts.4º–5º; atualização nominal de 5,4% pela revisão geral da Lei 25.804/2026, art.1º. Faixa ANS final: 59 anos ou mais. https://www.almg.gov.br/legislacao-mineira/texto/LEI/25143/2025/?cons=1',
   'tax':'Receita Federal, Tributação 2026; Leis 15.191/2025, 15.270/2025 e 9.430/1996, art.67 (dispensa mensal até R$10, não aplicada ao 13º exclusivo). https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2026',
   'vacation':'Férias usufruídas: remuneração + terço; IR em folha própria. RPPS não incide no terço (STF, Tema 163, RE 593.068); IPSEMG considera remuneração, excluídas verbas indenizatórias, conforme Lei 25.143/2025, art.6º. Não calcula férias indenizadas.'},
  'pension_bands':[{'upper':str(limit),'rate':rate} for limit,rate in zip(limits,['.11','.12','.13','.14','.15','.155'])]+[{'upper':None,'rate':'.16'}],
  'rgps_ceiling':'8475.55','pension_revaluation':history,
  'health':{'rate':'.032','minimum':'63.24','maximum':'527.00','child_under21':'63.24','child_21_to38':'94.86',
            'age_surcharge':'.01','surcharge_age':59,'minimum_wage':'1621.00',
            'low_income_rule':'statutory','thirteenth_incidence':True,'legal_exceptions':True},
  'tax_bands':[{'upper':u,'rate':r,'deduction':v} for u,r,v in [('2428.80','0','0'),('2826.65','.075','182.16'),('3751.05','.15','394.16'),('4664.68','.225','675.49'),(None,'.275','908.73')]],
  'tax_dependent':'189.59','tax_simplified':'607.20','reduction_enabled':True,'reduction_full_income':'5000.00',
  'reduction_full_max':'312.89','reduction_until':'7350.00','reduction_intercept':'978.62','reduction_slope':'.133145',
  'tax_withholding_minimum':'10.00','vacation_extra_pension':False,'vacation_extra_health':True,
  'evidence':evidence,
  'notes':['Simulação de servidor ativo EPPGG, uma fonte e um vínculo. O líquido depende das opções de regime, adesão e rubricas informadas.',
           'Limites RPPS recompostos da base legal de 2020 com os reajustes anuais RGPS; arredondamento a centavos em cada ano. A memória anual é exportada e o último limite confere com R$8.475,55 publicado em 2026.',
           'IPSEMG: valores nominais corrigidos em 5,4% por força do art.6º, §4º, da Lei 25.143/2025; adicional de 1 ponto percentual desde 59 anos com teto próprio, sem consumir o teto básico. Incidência também no 13º.',
           'Pais/irmãos exigem elegibilidade e dependência econômica confirmadas. Isenção especial de filho exige aprovação do IPSEMG, não apenas diagnóstico.',
           'IRRF é retenção estimada por folha, não imposto definitivo da declaração anual. A dispensa mensal de retenção até R$10 não é aplicada à tributação exclusiva do 13º.',
           'Projeção anual estática, com 12/12 avos, sem reajustes futuros e sem férias indenizadas. Pensão percentual, RRA e múltiplas fontes exigem rotinas específicas.',
           'Opção A real permanece não habilitada até conferência da manutenção das parcelas do enquadramento. Opção B e funções respeitam os cadastros de espécie.',
           'Status verified indica conferência dos parâmetros e fontes, não chancela governamental nem homologação do contracheque.'],
  'pending':['Confronto dos limites RPPS reconstruídos e seu arredondamento com tabela estadual/contracheque.',
             'Conferência do enquadramento da opção A dos comissionados.',
             'Múltiplos vínculos/fontes, RRA, aposentados e isenções fora das hipóteses implementadas.',
             'Confronto do resultado com o contracheque da competência e do vínculo.']})
 sys.path.insert(0,str(ROOT))
 from app.schemas import Parameters
 checked=Parameters.model_validate(data)
 (ROOT/'data/payroll-2026.json').write_text(checked.model_dump_json(indent=2)+'\n')
 print('Gerado:',checked.version,'Limites RPPS:',*[str(v) for v in limits])

if __name__=='__main__':build(Path(sys.argv[1]))
