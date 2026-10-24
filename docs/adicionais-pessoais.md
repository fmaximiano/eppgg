# Quinquênio e Adicional de Desempenho

A folha `eppgg-folha-real-2026-v5` calcula os adicionais pessoais e estima o ADE pelo índice de desempenho da Seplag, com a quantidade de avaliações satisfatórias informada ou estimada pelo ano de ingresso. Não altera as versões v1 a v4, que permanecem reproduzíveis, nem concede vantagens a partir da idade, data de ingresso ou tempo presumido.

A v4 adotava o aproveitamento integral da faixa (faixa × VB). A v5 aplica a fórmula oficial, em que a faixa é apenas o teto do índice.

## Referências e alcance da pesquisa

- Constituição de Minas Gerais, ADCT, art. 112, e EC estadual 57/2003: transição dos adicionais por tempo de serviço.
- Lei 14.693/2003, alterada pelas Leis 16.676/2007, 17.329/2008 e 19.553/2011: ADE.
- Decreto 44.503/2007, alterado pelos Decretos 44.732/2008, 46.032/2012 e 46.756/2015: regulamentação do ADE.
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

A tabela traz os máximos das faixas (P). O valor efetivo segue o índice da Seplag:

```
Índice ADE = P × [(0,3 × AI) + (0,7 × ADI)]      (AI e ADI divididas por 100)
Valor do ADE = VB × índice ADE × fração do mês
```

- **ADI do ADE:** a do último resultado concluído até a apuração. A atualização anual ocorre em 1º de outubro, por isso a ADI considerada no ADE pode não coincidir com a ADI vigente na GDPI. A interface tem um campo próprio ("ADI considerada no ADE"); em branco, usa a ADI da GDPI e a memória registra essa origem.
- **AI:** 70, nota atribuída quando o órgão não é signatário do Acordo de Resultados (item 18). Não há campo de AI para o ADE.
- **Nota mínima:** ADI do ADE abaixo de 70 não gera ADE no exercício (item 15).
- A quantidade de avaliações satisfatórias continua sendo uma hipótese (uma por ano completo, no cálculo por ingresso). Uma avaliação satisfatória não constitui, por si só, homologação do pagamento.

## Entradas e cálculo

O enquadramento pode ser: sem adicionais; quinquênio com direito preservado; ADE; opção formal pelo ADE com quinquênios já adquiridos. A coexistência exige o último enquadramento. A quantidade não aumenta automaticamente com o horizonte de carreira.

- Quinquênio: `base integral × 10% × quantidade reconhecida × fração do mês`.
- ADE por avaliações: seleciona a maior faixa (P) cujo mínimo de avaliações foi atingido. Abaixo de três avaliações, percentual zero; a partir de 35, teto de 70%. O percentual aplicado é P × índice de desempenho.
- ADE por ano de ingresso: quantidade estimada = `ano da competência − ano de ingresso`, considerando uma avaliação satisfatória por ano completo transcorrido. Sem dia/mês de ingresso, não se presume uma data exata de aniversário. Não conta o ano de ingresso como uma avaliação já concluída.
- Valor do ADE: `base integral × P × (0,3 × AI + 0,7 × ADI) / 100 × fração do mês`.

Ano posterior à competência, quantidade negativa ou fracionária e entradas conflitantes são rejeitados. A interface oferece as duas formas de estimativa, sem campo de percentual. Os percentuais informados em cenários anteriores permanecem reproduzíveis pela API e pela abertura de arquivos salvos.

A base padrão é o VB do cargo efetivo na posição escolhida. Bases específicas podem ser informadas separadamente para cada adicional, em valor mensal integral. A calculadora não reconstrói composição histórica, adicionais em cascata, atos anteriores à EC federal 19/1998 ou escolhas de base no exercício de comissão/função. Nessas situações, a base deve corresponder ao ato aplicável. A estimativa não decide o enquadramento nem os limites individuais da opção pelo ADE; esses direitos dependem do ato do vínculo.

As parcelas são arredondadas separadamente, compõem IR/RPPS/IPSEMG conforme o vínculo ativo simulado e integram férias e 13º. O terço segue as incidências próprias já existentes. O teto previdenciário, quando selecionado, é aplicado depois da soma da base. Não se inclui o adicional na base da GDPI ou do outro adicional.

Comparações, retroativos por competência, consolidação e exportações usam as mesmas parcelas do motor mensal. A memória JSON conserva quantidade, percentual, origem da base e fração; o CSV inclui a fórmula no fundamento. Na evolução de carreira, a base padrão acompanha o novo VB e bases específicas informadas permanecem fixas; a quantidade de avaliações e a faixa permanecem constantes para a mesma competência. As condições da projeção tornam essa hipótese explícita.

Cenários antigos permanecem sem adicionais. A interface desabilita os campos incompatíveis com o enquadramento e carrega simulações antigas sem herdar adicionais do formulário aberto.

## Exemplo de conferência

I-A, VB R$3.773,24; ADI95/AI90 na GDPI; dois quinquênios e ADE estimado por cinco avaliações satisfatórias (ou ingresso em2021 para competência2026), sem ADI própria do ADE (usa 95); IPSEMG para titular de35 anos:

- Quinquênio: R$754,65 (10% × 2 × VB).
- ADE: 3.773,24 × 10% × (0,3 × 0,70 + 0,7 × 0,95) = 3.773,24 × 8,75% = **R$330,16**.
- Bruto: R$7.502,06; RPPS: 771,0023 + (7.502,06 − 6.251,37) × 15% = R$958,61; IPSEMG: R$240,07; IRRF: (7.502,06 − 958,61) × 27,5% − 908,73 = R$890,72.
- Líquido: **R$5.412,66**.

Com ADI do ADE igual a 80, o ADE seria 3.773,24 × 10% × 0,77 = R$290,54; com 69,99, zero.

O exemplo pressupõe direito a ambas as parcelas e base no VB, sem outras verbas ou descontos.
