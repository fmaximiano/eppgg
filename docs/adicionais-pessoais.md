# Quinquênio e Adicional de Desempenho

A folha `eppgg-folha-real-2026-v4` calcula os adicionais pessoais e estima o ADE por ano de ingresso ou quantidade de avaliações satisfatórias. Não altera as versões v1/v2/v3 nem concede vantagens a partir da idade, data de ingresso ou tempo presumido.

## Referências e alcance da pesquisa

- Constituição de Minas Gerais, ADCT, art. 112, e EC estadual 57/2003: transição dos adicionais por tempo de serviço.
- Lei 14.693/2003, alterada pelas Leis 16.676/2007, 17.329/2008 e 19.553/2011: ADE.
- Decreto 44.503/2007, alterado pelos Decretos 44.732/2008, 46.032/2012 e 46.756/2015: regulamentação do ADE.
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

A publicação informa os máximos das faixas. Na simulação por ano ou quantidade, adota-se a hipótese explícita de **avaliações satisfatórias e aproveitamento integral da faixa**. Isso é uma estimativa: uma avaliação satisfatória não constitui, por si só, homologação do pagamento máximo. A memória e as condições do resultado identificam a hipótese; a ADI usada na GDPI não altera a faixa do ADE.

## Entradas e cálculo

O enquadramento pode ser: sem adicionais; quinquênio com direito preservado; ADE; opção formal pelo ADE com quinquênios já adquiridos. A coexistência exige o último enquadramento. A quantidade não aumenta automaticamente com o horizonte de carreira.

- Quinquênio: `base integral × 10% × quantidade reconhecida × fração do mês`.
- ADE por avaliações: seleciona a maior faixa cujo mínimo de avaliações foi atingido. Abaixo de três avaliações, percentual zero; a partir de 35, limite de 70%.
- ADE por ano de ingresso: quantidade estimada = `ano da competência − ano de ingresso`, considerando uma avaliação satisfatória por ano completo transcorrido. Sem dia/mês de ingresso, não se presume uma data exata de aniversário. Não conta o ano de ingresso como uma avaliação já concluída.
- Valor do ADE: `base integral × percentual da faixa × fração do mês`.

Ano posterior à competência, quantidade negativa ou fracionária e entradas conflitantes são rejeitados. A interface oferece as duas formas de estimativa, sem campo de percentual. Os percentuais informados em cenários anteriores permanecem reproduzíveis pela API e pela abertura de arquivos salvos.

A base padrão é o VB do cargo efetivo na posição escolhida. Bases específicas podem ser informadas separadamente para cada adicional, em valor mensal integral. A calculadora não reconstrói composição histórica, adicionais em cascata, atos anteriores à EC federal 19/1998 ou escolhas de base no exercício de comissão/função. Nessas situações, a base deve corresponder ao ato aplicável. A estimativa não decide o enquadramento nem os limites individuais da opção pelo ADE; esses direitos dependem do ato do vínculo.

As parcelas são arredondadas separadamente, compõem IR/RPPS/IPSEMG conforme o vínculo ativo simulado e integram férias e 13º. O terço segue as incidências próprias já existentes. O teto previdenciário, quando selecionado, é aplicado depois da soma da base. Não se inclui o adicional na base da GDPI ou do outro adicional.

Comparações, retroativos por competência, consolidação e exportações usam as mesmas parcelas do motor mensal. A memória JSON conserva quantidade, percentual, origem da base e fração; o CSV inclui a fórmula no fundamento. Na evolução de carreira, a base padrão acompanha o novo VB e bases específicas informadas permanecem fixas; a quantidade de avaliações e a faixa permanecem constantes para a mesma competência. As condições da projeção tornam essa hipótese explícita.

Cenários antigos permanecem sem adicionais. A interface desabilita os campos incompatíveis com o enquadramento e carrega simulações antigas sem herdar adicionais do formulário aberto.

## Exemplo de conferência

I-A, VB R$3.773,24; ADI95/AI90; dois quinquênios e ADE estimado por cinco avaliações satisfatórias (ou ingresso em2021 para competência2026); IPSEMG para titular de35 anos:

- Quinquênio: R$754,65; ADE: R$377,32.
- Bruto: R$7.549,22; RPPS: R$965,68; IPSEMG: R$241,58; IRRF: R$901,74.
- Líquido: **R$5.440,22**.

O exemplo pressupõe direito a ambas as parcelas, aproveitamento integral da faixa e base no VB, sem outras verbas ou descontos.
