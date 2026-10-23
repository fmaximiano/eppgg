"""Build explícito a partir das cópias oficiais conferidas em docs/dados-reais.md.

Uso: python scripts/build_career_data.py /caminho/official-research
Requer pdftotext para extrair os quatro PDFs; não acessa rede nem altera demonstrações.
Mudança de hash exige revisão humana antes de atualizar esta lista.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
 'salary':('743f79e2d8a0.pdf','fe4b4ab895e1f297d02b425453d69f8e5513aadc42341adfe12228acef02b428','seplag-eppgg-2026.pdf','https://www.mg.gov.br/system/files/media/planejamento/documento_detalhado/2026/grupo_1_-atualizacao-54-2026.pdf'),
 'dad_fgd_gted':('fe8ca154fbdb.pdf','7f9f465f53a99ad7577152a0c5aa8b84c0129c6e83100afa0d10022fd6a59dac','seplag-dad-fgd-gted-2026.pdf','https://www.mg.gov.br/system/files/media/planejamento/documento_detalhado/2026/dad_fgd_gted.pdf'),
 'dai':('d7934f59528a.pdf','8d9f00a0b54e05a54953f8cf7b737803cb0f9fd990b27eb821ade1d7e5561af3','seplag-dai-2026.pdf','https://www.mg.gov.br/system/files/media/planejamento/documento_detalhado/2026/dai.pdf'),
 'fgi_gtei':('c8ca46838728.pdf','b57dd63a6dc8869614dd4a56b0d761b2d570034b8d13ab48e17d1e419a916d6f','seplag-fgi-gtei-2026.pdf','https://www.mg.gov.br/system/files/media/planejamento/documento_detalhado/2026/fgi_gtei.pdf'),
 'gdpi':('c841c1c41f67.html','716ca4d0c13d4e798cc375bd545a844962268963678a26a729d85b8577790ea1','lei-13085-consolidada.html','https://www.almg.gov.br/legislacao-mineira/texto/LEI/13085/1998/?cons=1'),
 'regulation':('38966a1ffff1.html','ba5892582fe97b6fb4adf8a2f211ff98f73d392c67b159036d1ca0345669aa8a','decreto-46030-consolidado.html','https://www.almg.gov.br/legislacao-mineira/texto/DEC/46030/2012/?cons=1'),
 'direct':('825523b8b0b4.html','ce5d1afb724c827c2ba0c8eb7f02c725bd0ca760efe32f91b3621675df8411f4','lei-delegada-174-consolidada.html','https://www.almg.gov.br/legislacao-mineira/texto/LDL/174/2007/?cons=1'),
 'indirect':('1fbfb7f55c97.html','2eeaf8bcf9a6b964db4295f0cbf6e36eed7f83e4a4b5d8d37e33812c61d7bcbd','lei-delegada-175-consolidada.html','https://www.almg.gov.br/legislacao-mineira/texto/LDL/175/2007/?cons=1'),
 'revision':('6f5e1442de33.html','3195bd8b509a04e19808c46fcea0f9a1abbecd9717babeb33d5a44ec39818280','lei-25804-2026.html','https://www.almg.gov.br/legislacao-mineira/texto/LEI/25804/2026/'),
}

class TextParser(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.content=[]
 def handle_starttag(self,t,a):
  if t in ('script','style'):self.skip+=1
  if t in ('p','tr','br','div','h1','h2','h3'):self.content.append('\n')
 def handle_endtag(self,t):
  if t in ('script','style'):self.skip-=1
 def handle_data(self,d):
  if not self.skip and d.strip():self.content.append(d.strip()+' ')

def decimal(value):return value.replace('.','').replace(',','.')

def build(source_dir):
 texts={};evidence=[]
 target=ROOT/'data/sources';target.mkdir(exist_ok=True)
 for key,(original,digest,filename,url) in SOURCES.items():
  path=source_dir/original
  actual=hashlib.sha256(path.read_bytes()).hexdigest()
  if digest and actual!=digest:raise ValueError(f'Fonte alterada: {original}. Audite a nova publicação antes de importar.')
  if path.suffix=='.pdf':
   text=subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)
  else:
   parser=TextParser();parser.feed(path.read_text());text=''.join(parser.content)
  texts[key]=text
  shutil.copyfile(path,target/filename)
  evidence.append({'component':key,'url':url,'path':'data/sources/'+filename,'sha256':actual,'checked_at':'2026-10-23'})
 segment=texts['salary'].split('- EPPGG',1)[1].split('Gestor de Telecomunicações',1)[0]
 salaries={}
 for line in segment.splitlines():
  m=re.match(r'^\s*Superior\s+(I|II|III|IV|V)\s+(.+?)\s*$',line)
  if m:
   amounts=re.findall(r'\d[\d.]*,\d{2}',m[2]);assert len(amounts)==10
   salaries[m[1]]=[decimal(n) for n in amounts]
 assert len(salaries)==5
 segment=re.split(r'Pontuação\s+da GDPI por nível e grau',texts['gdpi'])[1].split('(Anexo')[0]
 points={}
 for match in re.finditer(r'\b(III|II|IV|V|I)\s+((?:\d[\d.]*\s+){9}\d[\d.]*)',segment):
  points[match[1]]=[str(int(n.replace('.',''))) for n in match[2].split()]
 assert len(points)==5
 source_urls={key:meta[3] for key,meta in SOURCES.items()}
 base_sources={'salary':'SEPLAG, Grupo I, p.2, vigência 01/01/2026; Lei 25.804/2026, art.3º, IV. '+source_urls['salary'],
  'gdpi':'Lei 13.085/1998, art.16, §§1º e 6º e Anexo V; Decreto 46.030/2012, Anexo II consolidado; P=50% da tabela. '+source_urls['gdpi'],
  'commission':'Tabelas SEPLAG publicadas em 2026; LD 174/2007 art.27 e LD 175/2007 art.20. '+source_urls['dad_fgd_gted'],
  'functions':'LD 174/2007, arts.9º e 15; LD 175/2007, arts.9º e 13. '+source_urls['direct'],
  'vacation':'Projeção estática de proventos; CF art.7º, VIII e XVII, e regras das rubricas. Descontos não apurados.'}
 commissions=[];functions=[]
 for key in ('dad_fgd_gted','dai','fgi_gtei'):
  rows=re.findall(r'^\s*((?:DAD|DAI|FGD|FGI|GTEI|GTE)-\d+)\s+([\d.]+,\d{2})\s+([\d.,]+)',texts[key],re.M)
  assert rows,key
  for code,value,unit in rows:
   family=code.split('-')[0]
   reference=('Lei Delegada 174/2007' if key=='dad_fgd_gted' else 'Lei Delegada 175/2007')
   source='SEPLAG, tabela publicada em 2026; '+reference+'. '+source_urls[key]
   if family in ('DAD','DAI'):
    commissions.append({'code':code,'kind':family,'amount':decimal(value),'allow_a':False,'allow_b':True,
       'a_keep_salary':False,'a_keep_gdpi':False,'b_keep_salary':True,'b_keep_gdpi':True,
       'optional_pension':True,'mandatory_pension':False,'pension_basis_a':'effective','pension_basis_b':'effective','source':source})
   else:
    kind='GTED' if family=='GTE' else family
    requires='DAD' if kind=='GTED' else ('DAI' if kind=='GTEI' else None)
    functions.append({'code':code.replace('GTE-','GTED-'),'kind':kind,'amount':decimal(value),
      'requires_commission_kind':requires,'allow_with_commission':requires is not None,
      'optional_pension':True,'tax':True,'health':True,'vacation':True,'thirteenth':True,'source':source})
 assert len(commissions)==52 and len(functions)==45
 from collections import Counter
 assert Counter(c['kind'] for c in commissions+functions)=={'DAD':12,'DAI':40,'FGD':15,'FGI':14,'GTED':8,'GTEI':8}
 positions=[{'level':level,'grade':grade,'salary':salaries[level][j],'points':points[level][j]} for level in ('I','II','III','IV','V') for j,grade in enumerate('ABCDEFGHIJ')]
 data={'version':'eppgg-remuneracao-real-2026-v1','status':'real','valid_from':'2026-01-01','valid_until':'2026-12-31',
  'effective_competence':'2026-01','source':'SEPLAG/MG e legislação consolidada ALMG, consultadas em 23/10/2026. Conferência documental de remuneração; não certifica folha líquida.',
  'verified_at':'2026-10-23','positions':positions,'sources':base_sources,'gdpi_factor':'0.0007','gdpi_reference_salary':salaries['V'][-1],
  'gdpi_point_share':'0.5','gdpi_min_adi':'70','gdpi_pension':True,'gdpi_health':True,'commissions':commissions,'functions':functions,
  'notes':['Valores de vencimento, pontuação e cargos/funções transcritos de fontes oficiais. Não são os valores fictícios do modo demonstrativo.',
           'GDPI: parcela variável usa 50% da pontuação do Anexo V (Lei 13.085/1998, art.16, §6º); a parcela fixa foi incorporada ao vencimento pela Lei 21.334/2014, art.9º.',
           'Cargos/funções dependem de designação e exercício compatíveis. A opção A real fica bloqueada até conferir a manutenção das parcelas no enquadramento concreto; a opção B segue as leis delegadas.',
           'Combinação FGD/FGI com comissão não habilitada; GTED exige DAD e GTEI exige DAI. GTED é o nome usado no aplicativo para a tabela GTE da administração direta.',
           'O intervalo até dezembro limita o ano disponibilizado; não declara que as tabelas nunca serão alteradas após a data de consulta.',
           'Projeções anuais brutas pressupõem direito integral e estabilidade da remuneração. Não há apuração de líquido neste modo.'],
  'pending':['Limites RPPS atualizados por competência e validação da base contributiva do enquadramento.',
             'Valores IPSEMG atualizados, regras especiais e conferência das incidências de cada rubrica.',
             'Integração e conferência dos descontos reais antes de liberar líquido mensal e anual.',
             'Enquadramento e manutenção de parcelas na opção A de cada cargo comissionado.'],
  'career_rules':{'source':'Instrução SEPLAG 001/2018, arts.17–21; simulação sobre pontos homologados, sem homologação documental automática.',
     'progression_cost':5,'promotion_cost':50,'interstice_years':4,'level_order':['I','II','III','IV','V'],
     'grade_order':list('ABCDEFGHIJ'),'annual_progression_limits':{'I':4,'II':3,'III':3,'IV':3,'V':3}},'evidence':evidence}
 (ROOT/'data/career-2026.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print('Importadas 50 posições, 52 cargos e 45 funções/gratificações, com fontes e hashes.')

if __name__=='__main__':build(Path(sys.argv[1]))
