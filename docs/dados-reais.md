# Dados reais da carreira · carga 2026

O aplicativo abre em **Dados reais**, usando valores transcritos de fontes oficiais consultadas em **23/10/2026**. A implantação carrega `data/career-2026.json` automaticamente, inclusive no Neon configurado por `DATABASE_URL`; não depende de uma importação manual posterior.

## O que foi inserido

| Dado | Cobertura | Fonte |
| --- | --- | --- |
| Vencimento básico | 50 posições, níveis I–V e graus A–J, jornada de 40h | SEPLAG, Grupo I, p.2; Lei 25.804/2026, art.3º, IV; vigência 01/01/2026 |
| Pontuação GDPI | 50 posições | Lei 13.085/1998 consolidada, Anexo V |
| Fator e quota GDPI | F=0,0007; quota variável de 50% da pontuação; VBref=R$13.538,20 (V-J) | Art.16, §§1º e 6º; Decreto 46.030/2012, Anexo II consolidado |
| DAD | 12 níveis | Tabela SEPLAG 2026; Lei Delegada 174/2007 |
| DAI | 40 níveis | Tabela SEPLAG 2026; Lei Delegada 175/2007 |
| FGD | 15 níveis | Tabela SEPLAG 2026; LD 174, arts.8º e 9º |
| FGI | 14 níveis | Tabela SEPLAG 2026; LD 175, arts.8º e 9º |
| GTED e GTEI | 8 níveis de cada | Tabelas SEPLAG 2026; LD 174, arts.14–15; LD 175, arts.12–13 |

São **52 cargos e 45 funções/gratificações**. Os valores foram lidos individualmente das tabelas; o motor não presume equivalência monetária entre códigos nem deriva a matriz por fatores de progressão.

Exemplos da carga: I-A R$3.773,24; I-B R$4.404,05; V-J R$13.538,20; DAD-6 R$4.004,97; DAD-12 e DAI-40 R$10.922,63; FGD-15 e FGI-14 R$3.197,81. Os valores de GTE são os publicados na tabela consultada, sem reajuste adicional presumido.

As cópias de quatro PDFs e cinco páginas legais estão em `data/sources/`. Cada evidência possui URL, data de conferência e SHA-256 no JSON. A página **Parâmetros e fontes** permite consultar todas as posições e todos os níveis, além de abrir os documentos oficiais. `/api/career-data` expõe o catálogo. `/api/parameters?mode=real&competence=2026-10` expõe o conjunto completo de folha vigente.

## Correção da GDPI

A Lei 21.334/2014 incorporou a parcela fixa ao vencimento a partir de 2015. O art.16, §6º da Lei 13.085/1998 determina que a parcela variável se aplique a **50% do limite máximo de pontos**. O Decreto 46.030/2012, Anexo II, na redação dada em 2016, manda respeitar essa disposição ao definir P.

Por isso, a carga mantém os pontos integrais do Anexo V e registra separadamente `gdpi_point_share: 0.5`. Não se paga novamente a parcela fixa:

```text
GDPI = pontos_tabela × 0,5 × 0,0007 × VB(V-J) × (0,6 × ADI/100 + 0,4 × AI/100)
```

I-A com ADI 95 e AI 90: 600 × 0,5 × 0,0007 × 13.538,20 × 0,93 = R$2.644,01; bruto de vencimento + GDPI = **R$6.417,25**. Notas, elegibilidade e proporção continuam sendo entradas, não valores fixos da carreira.

## Cargos e funções são espécies diferentes

FGD/FGI e GTE são pagas integralmente, sem aplicar automaticamente o percentual de 50% dos cargos comissionados. GTED exige DAD; GTEI exige DAI. No PDF da administração direta o código aparece como GTE; o aplicativo usa o prefixo GTED para distingui-lo de GTEI.

A opção B de comissão segue efetivo + 50%, conforme art.27 da LD 174 e art.20 da LD 175. A opção A real permanece bloqueada até conferir as parcelas preservadas no enquadramento concreto. Isso não equivale a negar a existência legal da opção A: o aplicativo ainda não a habilita nesse conjunto. Combinação FGD/FGI com comissão também permanece não habilitada no cadastro; não se presume uma autorização geral de acumulação. Os valores de cargos disponíveis não substituem o ato de nomeação/designação.

## Descontos e líquido

O catálogo remuneratório permanece imutável em `career_data_sets`. O conjunto completo `data/payroll-2026.json`, em `parameter_sets`, acrescenta as regras fiscais e é selecionado automaticamente pelo modo real. Não lê nem promove `data/demo.json`. Com parâmetros completos vigentes, comparações, evolução, retroativos estimados e exportações usam o líquido. Sem esses parâmetros, o catálogo isolado continua retornando líquido nulo.

Veja [líquido de 2026](liquido-2026.md) para as regras RPPS/IPSEMG/IRRF, reconstrução anual das faixas, evidências e limitações. O horizonte cadastrado vai até dezembro de 2026; não garante ausência de alteração normativa posterior à consulta. A opção A de comissão permanece desabilitada.

## Reprodução da carga

`scripts/build_career_data.py` lê cópias oficiais previamente obtidas, confere os hashes e extrai os PDFs com `pdftotext`. Não acessa rede durante a execução do aplicativo nem altera `data/demo.json`.

```bash
python scripts/build_career_data.py /caminho/para/as-copias-conferidas
```

Os nomes de entrada e hashes estão no script. Mudanças na fonte exigem revisão explícita do importador e nova versão/vigência. Versões já gravadas no banco são imutáveis; não altere o conteúdo mantendo o mesmo identificador. Na atualização para novo período, preserve o histórico e evite sobreposição de vigências.
