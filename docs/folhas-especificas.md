# Comissão A, RRA e múltiplos vínculos/fontes

Essas funcionalidades ficaram fora da primeira entrega do líquido porque exigiam regras específicas e entradas distintas. Agora possuem implementação e validação próprias, sem alterar as versões históricas dos dados.

## Comissão A

A LD 174/2007, art.27, I, e a LD 175/2007, art.20, I, permitem optar pelo vencimento do cargo comissionado. O Decreto 46.030/2012 consolidado, art.11, XI, prevê a GDPI durante exercício de cargo comissionado no Executivo estadual. A folha `eppgg-folha-real-2026-v2` habilita A para DAD/DAI: comissão integral + GDPI elegível, sem VB efetivo pago novamente. Não utiliza o art.20 revogado da Lei 13.085/1998 e não atribui automaticamente nota máxima à GDPI.

Exemplo I-A, ADI95/AI90, DAD-6: R$4.004,97 + R$2.644,01 = bruto R$6.648,98. A base RPPS de referência é R$6.417,25 sem opção contributiva. Com contribuição facultativa sobre a parcela comissionada, a base é R$6.648,98: soma-se somente o excedente da comissão ao VB substituído. Se a comissão for inferior ao VB, conserva-se a referência do efetivo. O regime com teto e a complementar continuam sendo escolhas separadas. Vantagens pessoais adicionais devem ser informadas como rubricas, com incidências próprias e fundamento do vínculo.

O comparador passa a mostrar sem comissão, A e B. GTED/GTEI respeitam a espécie do cargo e são integrais também em A. A carga histórica v1 continua inalterada e indisponibiliza A quando utilizada isoladamente; o resolvedor público seleciona a sucessora v2.

## RRA exclusivo de anos anteriores

Na aba **Evolução de carreira**, abra **Pagamento de RRA · anos anteriores**. A API é `POST /api/rra`. A rotina usa os valores do pagamento, não o somatório de líquidos mensais de origem. A página **Diferenças de competências anteriores** continua separada para apurar o crédito por competência.

A fonte é a Receita Federal, Perguntas e Respostas IRPF 2026, questão 251, pp. 131–132, e referências à Lei 7.713/1988, art.12-A, e IN RFB 1.500/2014, arts. 36–42. O manual foi preservado integralmente com SHA-256 em `data/sources/rfb-perguntas-respostas-2026.pdf`. Embora a edição trate da declaração do ano-calendário 2025, utiliza-se somente sua orientação de enquadramento; os valores da tabela vêm da competência de pagamento 2026 cadastrada.

Entradas: competência do pagamento, último ano de origem, número de meses, rendimentos tributáveis, isentos documentados, contribuição oficial, pensão dedutível, despesas judiciais dedutíveis e outros descontos efetivos. O número de meses inclui os meses de 13º abrangidos; para pagamentos parcelados, deve corresponder à parcela no demonstrativo, admitindo fração.

Base = tributáveis − despesas judiciais elegíveis − contribuição oficial − pensão dedutível. Multiplicam-se os limites e a parcela a deduzir da tabela mensal pelo número de meses; aplica-se a alíquota ao total da base. Não se arredonda previamente a renda mensal equivalente. Não há dependentes, simplificado mensal, redução de R$5 mil de 2026 nem dispensa de retenção até R$10 nessa apuração exclusiva.

Exemplo: R$60 mil tributáveis em 12 meses, sem deduções: IRRF = 60.000 × 27,5% − 908,73 × 12 = R$5.595,24. O resultado apresenta líquido antes e depois das despesas judiciais; não presume que honorários tenham sido retidos pelo banco no crédito. Contribuição previdenciária e demais descontos do RRA são informados a partir da apuração oficial, pois as competências de origem podem ter regras históricas diferentes.

O formulário rejeita valores do ano corrente, mês de pagamento sem tabela e deduções que superem o rendimento tributável. Não simula escolha pelo ajuste anual, juros/correção automáticos ou concessão de isenção. Juros isentos documentados podem compor o campo de valores isentos, separados da base tributável. A memória JSON inclui entradas, base, faixa multiplicada, fonte e ressalvas.

## Vínculos e fontes salariais

Na aba **Comparar**, salve cenários da mesma pessoa/competência e abra **Consolidar vínculos e fontes salariais**. Selecione os vínculos simultâneos e informe a fonte pagadora de cada um. Confirme que a acumulação é legal: a simulação não autoriza acumulação de cargos. Comissão deve integrar o cenário do vínculo efetivo, sem ser cadastrada como outro emprego.

`POST /api/multiple-employments` recebe de 2 a 5 entradas. Uma entrada contém `payer` e `scenario` EPPGG ou `reported` com valores salariais efetivos do contracheque. O primeiro vínculo deve ser EPPGG para definir competência, parâmetros e dados pessoais. A interface admite cenários salvos e uma fonte salarial adicional informada; a API admite até cinco entradas no total.

- RPPS estadual é calculado por cargo (LC 64/2002, art.27). Contribuições oficiais de outras fontes são informadas, sem aplicar tabela EPPGG a INSS/outro regime.
- IPSEMG é cobrado uma vez sobre a maior remuneração contributiva estadual, conforme Lei 25.143/2025, art. 6º, §8º, usando a mesma idade, adesão e família. Fontes salariais externas ao Estado não aumentam a base da saúde. Pela API, um contracheque estadual pode informar `reported.ipsemg_base` para participar da seleção da maior remuneração.
- IR mensal é recalculado por fonte pagadora: somam-se rendimentos e deduções legais dos seus vínculos e aplica-se dependentes/simplificado/redução uma vez. Fontes distintas têm retenções separadas. Use o mesmo identificador/nome para a mesma fonte; diferenças de maiúsculas e espaços são normalizadas, mas o aplicativo não identifica juridicamente a fonte pelo nome.
- Coparticipação, pensão e outros descontos devem ser os efetivamente cobrados em cada vínculo, sem repetir uma mesma cobrança. Os resultados por cargo exibem bases e contribuições; o líquido total usa o IR por fonte, evitando atribuir arbitrariamente esse imposto a um cargo.
- Com todas as fontes modeladas, há anual estático. Quando há contracheque informado, apresenta-se somente o mensal, pois não foram informadas suas folhas de férias e 13º. A retenção mensal conjunta não é o imposto definitivo da declaração anual.

Idade, adesão, família, dependentes fiscais, competência, modo e opção de projeção devem coincidir entre cenários da mesma pessoa; divergências retornam erro explicativo. A fonte salarial informada não serve para aluguéis, investimentos, rendimentos do exterior, RRA ou rendas sujeitas a regimes específicos. Sua contribuição oficial deve vir do contracheque, sem simulação automática de outra carreira/regime.

## Atualização no Railway/Neon

A inicialização inclui v2 automaticamente, com `supersedes` apontando para v1. As duas permanecem no banco e nenhuma tabela nem versão histórica é apagada. A alteração é apenas de parâmetros JSON, sem migração destrutiva de schema. Versões administrativas distintas são preservadas. A versão vigente do cálculo e a memória exportada permitem conferir a atualização após o deploy. Um novo deploy no Railway e acesso ao Neon do usuário dependem da configuração externa e não são atestados por testes locais.
