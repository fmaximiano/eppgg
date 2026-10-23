"""Sucessora explícita: mantém v1 imutável e habilita A com GDPI e RPPS por excedente."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.schemas import Parameters


def build(source):
    raw=source.read_bytes()
    expected='f3740385c07fa4dc52f8614d009dd5bd038fbeb8bd935f89da4e9bc26ed2a3b0'
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Manual RFB mudou; revise a fonte antes de gerar nova versão.')
    target=ROOT/'data/sources/rfb-perguntas-respostas-2026.pdf'
    target.write_bytes(raw)
    data=json.loads((ROOT/'data/payroll-2026.json').read_text())
    data['supersedes']=[data['version']]
    data['version']='eppgg-folha-real-2026-v2'
    for commission in data['commissions']:
        commission.update(allow_a=True,a_keep_gdpi=True,pension_excess_only_a=True)
        commission['source']+=' Opção A: vencimento comissionado, sem VB efetivo, com GDPI (Decreto 46.030/2012, art.11, XI). RPPS de referência do efetivo; opção contributiva somente sobre o excedente da comissão ao VB substituído.'
    data['sources']['commission']+=' Opção A conforme LD 174/2007, art.27, I, e LD 175/2007, art.20, I; GDPI preservada pelo Decreto 46.030/2012, art.11, XI. Não se aplica o revogado art.20 da Lei 13.085/1998.'
    data['sources']['rra']='RFB, Perguntas e Respostas IRPF 2026, questão 251, pp.131–132; Lei 7.713/1988, art.12-A; IN RFB 1.500/2014, arts.36–42. Tabela do mês do recebimento, sem importar os valores de 2025 do manual.'
    data['sources']['multiple_employments']='LC 64/2002, art.27: RPPS por cargo; Lei 25.143/2025, art.6º, §8º: IPSEMG sobre maior remuneração estadual. IR mensal por fonte pagadora, com ajuste anual posterior quando cabível.'
    data['evidence'].append({'component':'rra','title':'RFB, Perguntas e Respostas IRPF 2026, questão 251',
       'url':'https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf/@@download/file',
       'path':str(target.relative_to(ROOT)),'sha256':expected,'checked_at':'2026-10-23'})
    data['notes']=[n for n in data['notes'] if not n.startswith(('Opção A real','Projeção anual estática','Simulação de servidor'))]
    data['notes'] += ['Simulação de servidor ativo EPPGG. Múltiplos vínculos são consolidados em rotina própria, com acumulação legal confirmada pelo usuário; outras fontes salariais usam contribuições efetivas informadas do contracheque.',
      'Opção A: vencimento da comissão + GDPI elegível, sem pagamento duplicado do VB efetivo. Contribuição facultativa inclui somente o excedente da comissão ao VB substituído.',
      'RRA de anos anteriores possui apuração exclusiva própria pelo número de meses, com valores de contribuição oficial, pensão e despesas dedutíveis informados. Não confundir com diferenças nas competências de origem.',
      'Projeção anual estática, 12/12 avos, sem reajustes futuros nem férias indenizadas. Não é ajuste anual do IR.']
    data['pending']=['Confronto das faixas RPPS reconstruídas e seu arredondamento com tabela estadual/contracheque.',
       'Cálculo automático de previdência externa ao RPPS estadual, aposentados e isenções fora das hipóteses implementadas.',
       'Conferência dos atos de acumulação, opções contributivas e valores documentados do pagamento RRA.']
    p=Parameters.model_validate(data)
    (ROOT/'data/payroll-2026-v2.json').write_text(p.model_dump_json(indent=2)+'\n')
    print('Gerado:',p.version)

if __name__=='__main__':build(Path(sys.argv[1]))
