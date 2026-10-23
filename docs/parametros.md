# Administração dos parâmetros

A carga real remuneratória está separada deste contrato de folha: veja [dados-reais.md](dados-reais.md). `CareerData` contém somente remuneração e suas evidências e é carregado automaticamente; nunca recebe descontos fictícios como valores de preenchimento. O comando `app.manage schema` abaixo documenta os conjuntos completos de folha (`Parameters`).

`data/demo.json` exemplifica o contrato completo, mas contém números e incidências fictícios. **Não promova esse arquivo a `verified` sem substituir e auditar todos os campos.**

Gere o JSON Schema para validar arquivos produzidos por outra ferramenta:

```bash
.venv/bin/python -m app.manage schema > /tmp/eppgg-parameters.schema.json
```

Importe um conjunto em um processo com `DATABASE_URL` configurado:

```bash
.venv/bin/python -m app.manage import-parameters /caminho/parametros-auditados.json
```

Não há upload administrativo pela interface pública. A versão é imutável e a reimportação idêntica é segura. Conjuntos diferentes no mesmo status não podem sobrepor vigências; divida intervalos por competência e não atualize versões em lugar de preservar o histórico. Não existe transformação automática de normas ou reajuste presumido entre posições.

Campos necessários:

- `version`, `valid_from`, `valid_until`, `effective_competence`, `source`, `status`, `verified_at` e `notes`. Mantenha início de vigência alinhado à competência mensal de folha. Mudanças no meio do mês devem ser modeladas em cálculos separados com proporcionalidade explícita.
- `positions`: matriz completa das combinações válidas com `salary` e `points`, em strings decimais; nenhum valor é extrapolado pelo motor.
- `sources`: referências específicas para salary, gdpi, commission, pension, health, tax, vacation; registre publicação, artigo/anexo, URL e data da conferência.
- GDPI: fator e VB de referência legal da competência, nota mínima e incidências. `gdpi_point_share` registra a quota da pontuação utilizada: no conjunto real de 2026 é `0.5`, porque os pontos cadastrados são os limites integrais do Anexo V. A demonstração antiga mantém `1` como parte de suas fixtures fictícias; não copie isso para uma tabela real pós-incorporação da parcela fixa. O conjunto de 2015 requer F=0,0005; 2016, F=0,0006; desde 2017, referência histórica F=0,0007, sem atestar ausência de mudanças posteriores.
- `commissions`: valor, espécie, opções admitidas, retenção de parcelas em A/B, incidências e permissão de contribuição facultativa. Não generalize a regra de uma espécie para outra.
  `pension_basis_a/b: effective` preserva na base RPPS o vencimento/GDPI contributivos do efetivo mesmo quando não pagos naquela opção; `paid` considera só as parcelas pagas marcadas como contributivas. `mandatory_pension` inclui a parcela comissionada obrigatoriamente; `optional_pension` autoriza a escolha facultativa. A base de referência do efetivo também é mantida nas folhas projetadas de férias/13º, sem terço adicional sobre remuneração não paga. Se a norma exigir outra configuração de base nesses casos, a projeção exige adaptação específica e não deve ser liberada como auditada.
- `pension_bands`: limites crescentes e alíquotas progressivas; a última faixa tem `upper: null`. `rgps_ceiling` também depende da competência.
- `health`: percentuais, piso/teto, valores de filhos, marco etário, salário mínimo e incidência no 13º. `low_income_rule: unresolved` bloqueia o caso até dois salários mínimos. `standard` só pode ser usado se a aplicação da regra geral estiver juridicamente comprovada naquele conjunto; não significa implementação de todas as exceções.
- `tax_bands`: limites, alíquotas e parcelas; última faixa ilimitada. Cadastre dedução por dependente, simplificado e os parâmetros da redução de 2026. Para outras vigências, configure a redução conforme a lei; não replique a de 2026.
- `vacation_extra_pension` e `vacation_extra_health`: incidências sobre o terço; as demais incidências seguem a rubrica. Nas projeções atuais, a folha de férias preserva a remuneração mensal e acrescenta um terço das rubricas marcadas. Benefícios suspensos no mês de férias exigem cenários separados.
- `career_rules`: ordem explícita dos níveis/graus, custos, interstício, limites anuais e fonte. O simulador recebe saldos e pontos já homologados. Ainda não substitui a instrução de concessão nem audita a documentação dos eventos.

O modo `official` exige `status: verified` e `verified_at` preenchido. Esse marcador reflete a auditoria realizada pelo administrador, não uma certificação automática do aplicativo. O modo `demo` somente seleciona conjuntos `demo`; `provisional` serve para armazenar material em revisão e não é elegível para cálculos públicos nesta versão.

Confira o conjunto importado com casos de referência e contracheques anonimizados antes de usá-lo. A suíte automatizada valida o motor, mas não certifica dados oficiais que não foram fornecidos.

Funções possuem cadastro próprio em `functions`, separado de `commissions`. `Scenario.function` seleciona a rubrica integral e `function_pension` registra opção contributiva quando permitida. `requires_commission_kind` vincula GTED a DAD e GTEI a DAI; funções sem autorização de acumulação no cadastro bloqueiam a combinação com comissão. O percentual de 50% da opção B não incide sobre a função.
