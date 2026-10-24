# Validação da implementação

Executada no ambiente de desenvolvimento em 23/10/2026, incluindo o cálculo líquido real de 2026:

- `.venv/bin/python -m pytest -q`: **133 testes aprovados**. Cobertura das 50 posições reais, GDPI, faixas RPPS, regime com teto, opção contributiva em cargos/funções, IPSEMG por idade/renda/família, IRRF e redução, dispensa mensal de retenção, férias, 13º, comparações, carreira, retroativos e exportações. Um aviso de depreciação de dependência no TestClient.
- `python tests/browser_smoke.py`: Chromium em 1440 e 390 pixels. Abertura com líquido real, adesão IPSEMG, inclusão de filho, bloqueio de isenção sem aprovação, função integral, DAD/GTED, comparação pelo líquido, catálogo, demonstração, cenários salvos/editados, carreira, fontes, download e bloqueio de competência sem dados. A ampliação cobre A, consolidação de dois vínculos, fonte adicional do contracheque, RRA e download de suas memórias JSON. Sem erros JavaScript nem overflow horizontal nesses fluxos.
- `tests/postgres_smoke.py`: PostgreSQL 17 descartável com TLS. Criação do schema, carga real automática, cálculo HTTP com e sem IPSEMG, importação idempotente e persistência entre duas instâncias do aplicativo. Criptografia confirmada em `pg_stat_ssl`; contêiner e credenciais descartados após o teste. Não se usou banco de produção.
- Inicialização SQLite repetida com sucesso. Teste específico garante que a carga padrão não substitui versão administrativa verificada já existente.
- Cargas reproduzidas das cópias oficiais; hashes das nove fontes remuneratórias e das doze fontes fiscais adicionais conferidos. Importador fiscal fixa os hashes esperados. As referências de reajustes de 2024/2025 estão identificadas, mas suas cópias não foram obtidas; veja [memória do líquido](liquido-2026.md).
- `docker build --check .`: passou sem avisos. O Dockerfile usa instruções convencionais, sem o mount de segredo incompatível com o builder relatado pelo usuário. Essa checagem não executa a instalação de dependências nem equivale a um deploy.
- `node --check app/static/app.js`, compilação Python e `git diff --check` aprovados.

A etapa seguinte acrescentou testes da opção A nas 52 comissões, base RPPS por excedente, RRA exclusivo (meses fracionários, deduções e dispensa inaplicável), IR por fonte, saúde única, fontes salariais de contracheque e atualização imutável de v1 para v2. Há casos de rejeição de dados incompatíveis, proteção de versões administrativas e reprodução das memórias JSON.

O caso I-A, ADI95/AI90, sem dependentes fiscais, comissão ou extras, tem bruto R$6.417,25, RPPS R$795,88 e IRRF R$512,95: líquido R$5.108,42 sem IPSEMG ou R$4.903,07 com adesão e titular de 35 anos. As faixas progressivas são arredondadas após a soma; a memória conserva as parcelas sem arredondamento intermediário.

**Limites da validação:** sem novo deploy real no Railway, sem acesso ao projeto Neon do usuário e sem conciliação com contracheques. O PostgreSQL local confirma compatibilidade de driver/schema e persistência, não acesso a uma conta Neon específica. A reconstrução das faixas estaduais e seu arredondamento devem ser confrontados com tabela/folha estadual. Opção A, RRA de anos anteriores e consolidação de fontes salariais possuem rotinas e testes próprios; permanecem fora do escopo a autorização administrativa de acumulação, o cálculo automático de previdência de outras carreiras/regimes e as demais exceções descritas no README. Testes verificam regras implementadas; não constituem homologação governamental.

## Revisão da interface pública · 24/10/2026

- Suíte ampliada: **134 testes aprovados**, incluindo cobertura das normas essenciais do catálogo público e descrição/link institucional de cada referência. A planilha pública usa nomes de colunas e incidências em português, sem identificadores internos de versão.
- Chromium em 1440 e 390 pixels: cálculo, cargos/funções, IPSEMG, consolidação, RRA, cenários salvos e editados, retroativos por seletores de situação e período, pesquisa nas fontes e downloads. Sem erros JavaScript ou overflow horizontal nos fluxos verificados.
- Catálogo com 51 referências entre legislação, jurisprudência, orientações e tabelas oficiais, organizado em oito assuntos. O navegador verifica ausência de metadados de desenvolvimento e referências à conversa nas telas de resultados e fontes.
- Links federais e estaduais apontam aos portais oficiais. Alguns portais retornaram 403/503 neste ambiente; isso não constitui validação de disponibilidade permanente dos destinos. A Instrução Normativa SEPLAG remete à conferência pública do SEI/MG, com dados de autenticação do documento. As portarias de 2024/2025 remetem à consulta identificada no Diário Oficial da União.
- Sem mudança nas fórmulas, parâmetros imutáveis ou schema do banco nesta revisão.

## Organização dos cargos e funções

- DAD/GTED e DAI/GTEI em grupos próprios, com FGD/FGI separados. O catálogo de remuneração segue a mesma ordem.
- Chromium em 1440 e 390 pixels: seleção de DAD e DAI, habilitação da gratificação correspondente, bloqueio e limpeza de FGD/FGI, troca entre as famílias, reabilitação ao retirar o cargo, limpeza do formulário e recuperação de cenários salvos. Sem erros JavaScript ou overflow horizontal nos fluxos verificados.
- A seleção fica desabilitada durante o carregamento para evitar perda de escolhas ao limpar o formulário. Contribuições facultativas são limpas quando a parcela correspondente deixa de estar selecionada.
- Suíte de cálculo e APIs: **134 testes aprovados**. Checagem JavaScript e `git diff --check` aprovadas. Nenhuma alteração nas fórmulas ou nos parâmetros legais.
