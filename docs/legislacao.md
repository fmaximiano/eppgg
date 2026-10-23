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

Ainda faltam a matriz salarial oficial por competência, validação atual dos pontos/VBref GDPI, tabelas e elegibilidade dos comissionados, limites monetários RPPS/RGPS, regras atualizadas e exceções do IPSEMG, incidências e reflexos especiais, conferência da legislação federal de IR de 2026 e confronto com folhas oficiais. A Lei 25.804/2026 e as normas atuais RPPS/IPSEMG citadas na especificação não estão entre os anexos recebidos.

A tentativa de consulta aos sites `www.mg.gov.br` e `www.almg.gov.br` neste ambiente recebeu HTTP 403 do proxy de rede. Isso não comprova ausência das normas; impede apenas a conferência externa nesta execução. O aplicativo permanece demonstrativo e bloqueia o modo oficial sem importação auditada.

Fontes para conferência: [ALMG](https://www.almg.gov.br/), [SEPLAG/MG](https://www.mg.gov.br/planejamento/pagina/gestao-de-pessoas/carreiras-e-remuneracao/tabelas-de-vencimento-basico), [IPSEMG](https://www.ipsemg.mg.gov.br/), [Receita Federal](https://www.gov.br/receitafederal/pt-br).
