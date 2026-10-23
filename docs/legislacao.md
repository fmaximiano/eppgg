# Anexos recebidos e rastreabilidade

Os 11 PDFs enviados foram preservados em `docs/legislacao/`. `data/legal-sources.json` contém os nomes e SHA-256 calculados dos arquivos originais. Nenhum texto de documento é tratado como instrução de execução do projeto.

## Constatações históricas

| Documento | Uso na análise | Cuidado de vigência |
| --- | --- | --- |
| Lei 18.974/2010 | Carreira, desenvolvimento, matriz histórica no Anexo IV | A compilação recebida foi impressa em 2019; o Anexo IV remete à Lei 21.334/2014. Não é tabela de 2026. |
| Lei 13.085/1998 | Anexo V com pontos GDPI por nível/grau | O arquivo informa atualização em 27/06/2014 e redação da Lei 20.336/2012. |
| Lei 20.336/2012 | Alterações de carreira e pontos | Conferir texto consolidado e alterações posteriores. |
| Lei 21.334/2014 | Alterações remuneratórias e desenvolvimento | Não aplicar reajustes posteriores presumidos. |
| Decreto 46.030/2012 | Regulamento da carreira e da GDPI | Texto original contém dispositivos depois alterados/revogados. |
| Decreto 46.640/2014 | Fórmula GDPI, notas 60%/40%, mínimo individual de 70% | Anexo com F de 0,0005 (2015), 0,0006 (2016), 0,0007 (desde 2017). |
| Decreto 46.956/2016 | Descrição de P e revogação do inciso V do art.11 | P remete ao Anexo V da Lei 13.085/1998, respeitado §6º do art.16. |
| Decreto 47.081/2016 | Curso integral com ônus na origem incluído no art.10, V; revogação do art.9º, §7º | Não transportar a vedação anterior de curso integral para competências posteriores. |
| Instrução SEPLAG 001/2018 | Saldos separados, pontos por evento, requerimentos e posicionamento | Homologação e janelas não são automatizadas. Promoção precede progressão; primeiro grau com vencimento superior no novo nível. |
| Decreto 45.600/2011 | Referência histórica adicional | Não selecionado automaticamente para 2026. |
| Lei 15.961/2005 | Referência histórica adicional | Exige cotejo com alterações posteriores. |

As 50 posições e seus valores históricos foram transcritos para `data/historical-reference.json`, com referências específicas. Esse arquivo não contém os demais tributos e nunca é carregado pelo motor como conjunto vigente. Os dados demonstrativos estão separados e explicitamente rotulados como fictícios.

## Pendências materiais

A matriz salarial, pontos/VBref GDPI e tabelas DAD/DAI/FGD/FGI/GTED/GTEI de 2026 foram acrescentadas após consulta oficial. Ainda faltam a conferência completa dos limites monetários e bases RPPS/RGPS, regras atualizadas e exceções IPSEMG, incidências e reflexos especiais, manutenção das parcelas na opção A dos comissionados e confronto da folha líquida com contracheques. A Lei 25.804/2026 e normas atuais RPPS/IPSEMG não estavam nos anexos originais, mas seus textos públicos foram consultados nesta etapa.

A primeira tentativa de consulta aos sites MG/ALMG recebeu 403 do proxy. Na etapa seguinte de inclusão dos dados reais, essas fontes ficaram acessíveis e foram consultadas: a matriz salarial, os pontos GDPI e os valores de cargos/funções de 2026 estão em [dados-reais.md](dados-reais.md), com cópias preservadas em `data/sources/`. O Portal do Servidor ainda respondeu 403; descontos e líquido reais continuam pendentes. Não se deve mais interpretar a transcrição histórica como o único dado disponível.

Fontes para conferência: [ALMG](https://www.almg.gov.br/), [SEPLAG/MG](https://www.mg.gov.br/planejamento/pagina/gestao-de-pessoas/carreiras-e-remuneracao/tabelas-de-vencimento-basico), [IPSEMG](https://www.ipsemg.mg.gov.br/), [Receita Federal](https://www.gov.br/receitafederal/pt-br).
