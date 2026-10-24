# Horizonte · Calculadora salarial EPPGG-MG

Aplicação web em **Python 3.12 + FastAPI**, com interface em português e persistência de parâmetros em **PostgreSQL/Neon**. Implantação por Docker no **Railway**. Não exige cadastro para simular, exportar ou guardar até três cenários no navegador.

**Líquido estimado de 2026 disponível no modo Dados reais.** A remuneração contempla 50 posições, 52 cargos e 45 funções/gratificações. A folha aplica RPPS progressivo, IPSEMG conforme adesão e família, IRRF com redução de 2026 e descontos informados. O conjunto completo é carregado automaticamente no banco, separado das fixtures demonstrativas. [Regras, memória dos reajustes e limites do líquido](docs/liquido-2026.md). Não é uma calculadora oficial de folha.

## Rodar localmente

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m app.manage init-db
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Sem `DATABASE_URL`, usa SQLite (`eppgg.db`, ignorado pelo Git). Não precisa de credenciais para desenvolver. O servidor inicializa as tabelas e insere, de maneira idempotente, o conjunto demonstrativo, o catálogo remuneratório e a folha real de 2026. A carga real também ocorre automaticamente em um deploy com Neon; não requer importação manual após o deploy.

Para usar Neon, configure `DATABASE_URL` no processo com a connection string do banco e `sslmode=require` (ou `verify-full` com a cadeia confiável). Não imprima nem versione a URL. `.env.example` é apenas um modelo; para carregar um `.env` local ignorado, use `uvicorn ... --env-file .env`. A conexão usa psycopg 3; URLs `postgresql://` são convertidas para o driver correto. Valores de `sslmode` que desativam TLS são rejeitados.

## O que já funciona

- Núcleo mensal: matriz explícita de nível/grau, GDPI por avaliações, quota legal explícita da pontuação (50% no conjunto real de 2026), limiar individual de 70%, ausência de AI, hipótese legal de notas de 70% e proporcionalidade.
- Adicionais pessoais: quinquênios reconhecidos e ADE por ano de ingresso ou quantidade de ADI/AED satisfatórias, com aproveitamento integral da faixa, com bases específicas e reflexos no líquido, férias e 13º. [Regras e limites](docs/adicionais-pessoais.md).
- Comissões: alternativas A/B habilitadas por cargo, retenção de vencimento/GDPI e contribuição facultativa independente. Não presume que DAD, DAI e funções tenham o mesmo enquadramento.
- RPPS por faixas progressivas, regime com teto do RGPS e simulação de contribuição complementar sobre o excedente.
- IPSEMG: adesão, titular, cônjuge, filhos, pisos, tetos, adicional etário e teto conjunto com filhos menores. Dependentes do IR separados dos beneficiários de saúde.
- IRRF: deduções legais versus simplificado, dependentes, pensão elegível, complementar elegível e redução de 2026 pela renda tributável anterior às deduções. IPSEMG não deduzido como previdência.
- Rubricas configuráveis com fonte, natureza, proporcionalidade e incidências separadas em IR/RPPS/IPSEMG/férias/13º. Consignações após as bases.
- Memória auditável em JSON e demonstrativo em CSV, sem fórmulas executáveis em células fornecidas pelo usuário.
- Cenários locais: salvar, editar, duplicar, importar exportação JSON e comparar até três, com diferenças absolutas/percentuais e indicação do maior líquido mensal/anual.
- Projeção estática: 11 folhas normais + 1 folha de férias com terço + 13º separado; rubricas e bases próprias. Não equivale à apuração efetiva do ano civil.
- Evolução simples por seleção de posição e gráfico de diferença acumulada; simulação de atos com **pontos já homologados**, saldos separados, interstício, precedência da promoção, grau com vencimento superior, limites anuais e datas administrativas distintas.
- Retroativos: diferenças estimadas por competência de origem. Rotina separada de RRA exclusivo para anos anteriores, com meses, contribuição oficial, pensão e despesas judiciais informadas.
- Vínculos/fontes: consolidação dos cenários salvos, RPPS por cargo, IPSEMG único e IR por fonte pagadora. Outras fontes salariais usam contribuições e valores efetivos do contracheque. Exporte a memória JSON de ambas as rotinas.

## Limites atuais

Não estão implementados: homologação automática de títulos/eventos de carreira, todas as janelas/condições de protocolo, isenções fora das hipóteses cadastradas, aposentadorias/paridade, conciliação/importação de contracheques, pensão percentual com reflexos automáticos, férias e 13º proporcionais por avos ou benefícios com calendário de dias úteis. Alimentação/transporte podem ser lançados como rubricas com valor total, não são concedidos automaticamente.

No conjunto de 2026, IPSEMG inclui a regra até dois salários mínimos, adicional desde 59 anos com teto próprio, filhos com isenção aprovada e pais/irmãos com elegibilidade confirmada. Condição especial do titular e enquadramentos não cadastrados continuam bloqueados. Não se presume aprovação administrativa.

As notas de GDPI devem corresponder ao período legal de avaliação. O app não decide automaticamente o enquadramento funcional em afastamentos. A projeção anual pressupõe remuneração estável e direito integral às folhas; não prevê reajustes ou atos futuros. O gráfico representa valores constantes.

## Parâmetros e legislação

- [Dados reais inseridos em 2026](docs/dados-reais.md).
- [Revisão dos anexos e pendências](docs/legislacao.md).
- [Importar e versionar tabelas](docs/parametros.md).
- [Implantar no Railway com Neon](docs/deploy.md).
- `docs/legislacao/`: os 11 PDFs recebidos, preservados; checksums em `data/legal-sources.json`.
- `data/payroll-2026-v4.json`: folha vigente, com ADE estimado por avaliações satisfatórias ou ano de ingresso. As versões v1, v2 e v3 permanecem como histórico imutável, substituídas explicitamente pela v4. Cenários anteriores com percentual informado continuam reproduzíveis.
- `data/career-2026.json`: carga real de 2026, 50 posições e 97 cargos/funções; cópias das fontes em `data/sources/`.
- `data/historical-reference.json`: 50 posições transcritas do Anexo IV da Lei 18.974/2010 e do Anexo V da Lei 13.085/1998. **Referência histórica isolada, nunca usada automaticamente como tabela de 2026.**

## Front-end

- `app/templates/index.html` e `app/static/{app.js,style.css}`: todas as abas. Cada aba tem endereço próprio (`/#compare`, `/#career`, `/#hypotheses`, `/#sources`).
- `app/static/hypotheses.js`: aba de cenários hipotéticos, que usa o cenário preenchido na Calculadora.
- `style.css` é dividido em seções numeradas (tokens, base, componentes, uma seção por aba, responsivo e impressão). Use os tokens do `:root`: cores, escala de espaçamento (`--space-*`) e raios (`--radius-*`), sem valores soltos.
- Formatação com [Prettier](https://prettier.io) (`.prettierrc.json`): `npx prettier --write app/static app/templates`.

## Testes

```bash
.venv/bin/python -m pytest -q
```

Há testes de valores calculados independentemente, limites de faixas, todas as 50 posições demonstrativas, incidências, comissionamento, validação de entradas, versionamento, APIs e exportações. CI em GitHub Actions roda a suíte e constrói a imagem.

Testes opcionais adicionais:

```bash
# Com servidor iniciado e Playwright/Chromium disponíveis:
python tests/browser_smoke.py
python tests/browser_personal_additions.py
# Para outro executável/servidor: CHROMIUM_PATH e APP_URL.

# Banco de teste PostgreSQL com TLS; nunca aponte para produção:
# Injete TEST_DATABASE_URL pelo ambiente, sem expor a credencial.
.venv/bin/python -m tests.postgres_smoke
```

`tests/postgres_smoke.py` insere uma versão sintética de teste, verifica persistência entre instâncias e conexão TLS e remove essa versão ao terminar. Não audita regras legais reais.

A interface inicia no modo real; a API mantém `mode: demo` como padrão para compatibilidade com os cenários e integrações anteriores. Envie `mode: real` para calcular o líquido com os parâmetros reais vigentes.

API: contrato em `/openapi.json`, saúde em `/health`; operações de cálculo em `/api/rra`, `/api/multiple-employments`, `/api/calculate`, `/api/compare`, `/api/commission-options`, `/api/career`, `/api/career/act`, `/api/retroactive`, `/api/hypotheses`, `/api/hypotheses/level-vi` e `/api/export/{json|csv}`. Não existe endpoint público para modificar parâmetros. Cenários são enviados para cálculo, mas não gravados no banco pelo servidor; o navegador guarda as entradas em armazenamento local.

A opção A usa vencimento comissionado + GDPI elegível, substituindo o VB do efetivo. RPPS conserva a referência do cargo efetivo; contribuição facultativa considera somente o excedente da comissão ao VB substituído. [Regras de comissão, RRA e vínculos](docs/folhas-especificas.md).

A interface pública reúne a legislação da carreira e as publicações oficiais em uma página com busca por norma ou assunto, descrições e links institucionais. O catálogo editorial fica em `data/public-sources.json`, separado dos parâmetros imutáveis de cálculo. Os retroativos usam seleção de cenários e período; as opções técnicas de demonstração continuam apenas na API para compatibilidade.

A navegação e o botão de salvar ficam no cabeçalho. A avaliação inicial utiliza somente ADI/AED, com a nota institucional vazia e inativa. Campos dependentes de adesão, regime, cargo, função e valores informados são habilitados conforme a situação. Os formulários de ato com saldos homologados e pagamento de RRA foram retirados da interface pública; os contratos de API existentes permanecem disponíveis.
