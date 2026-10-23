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

A matriz salarial, pontos/VBref GDPI e tabelas DAD/DAI/FGD/FGI/GTED/GTEI de 2026 foram acrescentadas após consulta oficial. O conjunto completo de folha foi adicionado posteriormente: veja [dados reais](dados-reais.md) e [regras do líquido](liquido-2026.md). LC 64/2002 consolidada, Lei 25.143/2025, Decreto 48.981/2025, tabela RFB e índices RGPS complementam os anexos históricos. As cópias consultadas estão em `data/sources/`.

As faixas RPPS de 2026 foram recompostas pela regra de atualização anual, com memória explícita. Não se apresentam como transcrição de uma tabela estadual obtida no Portal do Servidor, que respondeu 403 no ambiente. A opção A foi habilitada na folha v2 após cotejar LD 174, art.27, LD 175, art.20, e Decreto 46.030/2012, art.11, XI; não se aplicou o revogado art.20 da Lei 13.085. O manual RFB 2026, questão251, fundamenta a rotina de RRA. Permanecem a validação com contracheques e hipóteses especiais fora do escopo. Os anexos históricos não atestam por si só vigência ou valores de 2026.
