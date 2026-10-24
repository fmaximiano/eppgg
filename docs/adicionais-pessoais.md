# Quinquênio e Adicional de Desempenho

A folha `eppgg-folha-real-2026-v6` calcula os adicionais pessoais e estima o ADE como faixa × ADI, com a quantidade de avaliações satisfatórias informada ou estimada pelo ano de ingresso. Não altera as versões v1 a v5, que permanecem reproduzíveis, nem concede vantagens a partir da idade, data de ingresso ou tempo presumido.

Histórico do ADE nas versões:

- v4: aproveitamento integral da faixa (faixa × VB).
- v5: fórmula do Anexo II com AI fixada em 70 (redação de 2012 do § 8º do art. 4º).
- v6: sem avaliação institucional, ADI considerada integralmente (redação do Decreto 46.756/2015). Conferida com contracheque: IV-J, ingresso em 2009, ADI 94,28 → R$3.158,13.

## Referências e alcance da pesquisa

- Constituição de Minas Gerais, ADCT, art. 112, e EC estadual 57/2003: transição dos adicionais por tempo de serviço.
- Lei 14.693/2003, alterada pelas Leis 16.676/2007, 17.329/2008 e 19.553/2011: ADE.
- Decreto 44.503/2007, alterado pelos Decretos 44.732/2008, 46.032/2012 e 46.756/2015: regulamentação do ADE.
- Decreto 44.503/2007, art. 4º e Anexo II: ADE = P × VB × [(0,3 × AI) + (0,7 × ADI)]. Cópia consolidada até 2014 publicada pela UEMG, preservada em `data/sources/decreto-44503-consolidado-2014.pdf`.
- [Decreto 46.756/2015](https://www.almg.gov.br/legislacao-mineira/texto/DEC/46756/2015/): nova redação do § 8º do art. 4º do Decreto 44.503/2007. Se o órgão não passou por Avaliação de Desempenho Institucional (o Acordo de Resultados foi extinto), "será considerado, integralmente, o resultado da Avaliação de Desempenho Individual". O portal da ALMG não pôde ser baixado para arquivamento; a pendência está registrada na v6.
- Seplag, "Adicional de Desempenho · perguntas e respostas" (itens 5, 11, 13, 15 e 18): fórmula do índice, pesos, ADI considerada, nota mínima e AI 70 para órgão sem Acordo de Resultados. Cópia publicada pelo Sindppen-MG, preservada em `data/sources/seplag-ade-perguntas-respostas.pdf`, SHA-256 `77030f8ca05df78758636287e76ed2e9ca59a5c6421d2453a4d285a39a5108ff`.
- [Orientação oficial da Seplag sobre ADE](https://www.mg.gov.br/system/files/media/planejamento/documento_detalhado/2022/gestao-de-pessoas/direitos-e-deveres-do-servidor/adicional_de_desempenho_ade.pdf): cópia preservada em `data/sources/seplag-adicional-desempenho.pdf`, SHA-256 `4987706b5947e7e233542482d56cb63fbe1dd2c7fb4565f1640f1fc3e044353e`.

A orientação oficial foi consultada em 24/10/2026. Ela confirma destinatários, conclusão do probatório, opção pelo ADE em substituição a futuras aquisições por tempo de serviço, atualização em outubro e as faixas máximas abaixo. Os endereços dos textos consolidados da ALMG retornaram HTTP 503 durante a pesquisa; não são apresentados como cópias integrais baixadas ou revalidadas. As alterações do ADE listadas no catálogo são as indicadas expressamente pela Seplag, sem inferir alterações posteriores não consultadas.

| Avaliações satisfatórias | Máximo sobre o VB |
| --- | --- |
| 3 | 6% |
| 5 | 10% |
| 10 | 20% |
| 15 | 30% |
| 20 | 40% |
| 25 | 50% |
| 30 | 60% |
| 35 | 70% |

A tabela traz os máximos das faixas (P). A fórmula geral do Anexo II é `P × [(0,3 × AI) + (0,7 × ADI)]`. Sem avaliação institucional, a ADI vale integralmente, e o cálculo da v6 é:

```
Índice ADE = P × ADI                     (ADI dividida por 100)
Valor do ADE = VB × índice ADE × fração do mês
```

- **ADI do ADE:** a do último resultado concluído até a apuração. A atualização anual ocorre em 1º de outubro, por isso a ADI considerada no ADE pode não coincidir com a ADI vigente na GDPI. A interface tem um campo próprio ("ADI considerada no ADE"); em branco, usa a ADI da GDPI e a memória registra essa origem.
- **AI:** não entra no cálculo. A nota 70 do FAQ da Seplag (item 18) reflete a redação de 2012, substituída pelo Decreto 46.756/2015. Não há campo de AI para o ADE.
- **Nota mínima:** ADI do ADE abaixo de 70 não gera ADE no exercício (item 15).
- A quantidade de avaliações satisfatórias continua sendo uma hipótese (uma por ano completo, no cálculo por ingresso). Uma avaliação satisfatória não constitui, por si só, homologação do pagamento.

## Entradas e cálculo

O enquadramento pode ser: sem adicionais; quinquênio com direito preservado; ADE; opção formal pelo ADE com quinquênios já adquiridos. A coexistência exige o último enquadramento. A quantidade não aumenta automaticamente com o horizonte de carreira.

- Quinquênio: `base integral × 10% × quantidade reconhecida × fração do mês`.
- ADE por avaliações: seleciona a maior faixa (P) cujo mínimo de avaliações foi atingido. Abaixo de três avaliações, percentual zero; a partir de 35, teto de 70%. O percentual aplicado é P × ADI.
- ADE por ano de ingresso: quantidade estimada = `ano da competência − ano de ingresso`, considerando uma avaliação satisfatória por ano completo transcorrido. Sem dia/mês de ingresso, não se presume uma data exata de aniversário. Não conta o ano de ingresso como uma avaliação já concluída.
- Valor do ADE: `base integral × P × ADI / 100 × fração do mês`.

Ano posterior à competência, quantidade negativa ou fracionária e entradas conflitantes são rejeitados. A interface oferece as duas formas de estimativa, sem campo de percentual. Os percentuais informados em cenários anteriores permanecem reproduzíveis pela API e pela abertura de arquivos salvos.

A base padrão é o VB do cargo efetivo na posição escolhida. Bases específicas podem ser informadas separadamente para cada adicional, em valor mensal integral. A calculadora não reconstrói composição histórica, adicionais em cascata, atos anteriores à EC federal 19/1998 ou escolhas de base no exercício de comissão/função. Nessas situações, a base deve corresponder ao ato aplicável. A estimativa não decide o enquadramento nem os limites individuais da opção pelo ADE; esses direitos dependem do ato do vínculo.

As parcelas são arredondadas separadamente, compõem IR/RPPS/IPSEMG conforme o vínculo ativo simulado e integram férias e 13º. O terço segue as incidências próprias já existentes. O teto previdenciário, quando selecionado, é aplicado depois da soma da base. Não se inclui o adicional na base da GDPI ou do outro adicional.

Comparações, retroativos por competência, consolidação e exportações usam as mesmas parcelas do motor mensal. A memória JSON conserva quantidade, percentual, origem da base e fração; o CSV inclui a fórmula no fundamento. Na evolução de carreira, a base padrão acompanha o novo VB e bases específicas informadas permanecem fixas; a quantidade de avaliações e a faixa permanecem constantes para a mesma competência. As condições da projeção tornam essa hipótese explícita.

Cenários antigos permanecem sem adicionais. A interface desabilita os campos incompatíveis com o enquadramento e carrega simulações antigas sem herdar adicionais do formulário aberto.

## Exemplo de conferência

I-A, VB R$3.773,24; ADI95/AI90 na GDPI; dois quinquênios e ADE estimado por cinco avaliações satisfatórias (ou ingresso em2021 para competência2026), sem ADI própria do ADE (usa 95); IPSEMG para titular de35 anos:

- Quinquênio: R$754,65 (10% × 2 × VB).
- ADE: 3.773,24 × 10% × 0,95 = **R$358,46**.
- Bruto: R$7.530,36; RPPS: 771,0023 + (7.530,36 − 6.251,37) × 15% = R$962,85; IPSEMG: R$240,97; IRRF: (7.530,36 − 962,85) × 27,5% − 908,73 = R$897,34.
- Líquido: **R$5.429,20**.

Com ADI do ADE igual a 80, o ADE seria 3.773,24 × 10% × 0,80 = R$301,86; com 69,99, zero.

Caso conferido com contracheque: IV-J (VB R$11.165,80), ingresso em 2009 (17 avaliações, faixa 30%), ADI 94,28 → 11.165,80 × 30% × 0,9428 = **R$3.158,13**.

O exemplo pressupõe direito a ambas as parcelas e base no VB, sem outras verbas ou descontos.
