# Validação desta implementação

Executada no ambiente de desenvolvimento, em 23/10/2026:

- Suíte: `.venv/bin/python -m pytest -q` — **61 passed**. Um aviso de depreciação de dependência no TestClient; nenhuma falha.
- `tests/browser_smoke.py` — passou em Chromium, larguras de 1440 e 390 pixels. Fluxos de cálculo, GDPI abaixo do mínimo, cenários salvos/editados, comparação, evolução simples, fontes, download e bloqueio sem tabelas oficiais. Sem erros JavaScript ou overflow horizontal nesses fluxos.
- `tests/postgres_smoke.py` — passou em PostgreSQL 17 descartável com TLS: criação de schema, importação idempotente, persistência entre instâncias e cálculo HTTP. Conexão criptografada confirmada em `pg_stat_ssl`. Recursos de teste removidos ao terminar.
- Imagem Docker original construída com dependências travadas e hashes verificados, usando a CA confiável do proxy no ambiente de desenvolvimento. Após relato de incompatibilidade do construtor do Railway, o mount de segredo usado nessa validação foi removido do Dockerfile de implantação. A imagem original testada e a correção de compatibilidade são verificações distintas; nenhum deploy real no Railway foi validado nesta execução. Nenhuma verificação de certificado ou checksum foi desativada.
- Imagem executada como usuário não root, usando `PORT=9070`; `/health` e `/api/calculate` responderam corretamente. O teste inicial encontrou permissões restritas nos arquivos copiados; corrigido com leitura explícita para o usuário da imagem e revalidado.
- `node --check app/static/app.js` e compilação Python passaram.
- Correção de compatibilidade Railway: `docker build --check .` passou sem avisos após remover o mount de segredo. Essa checagem valida o Dockerfile, mas não executa a instalação de dependências nem substitui o redeploy no Railway.
- Checksums dos 11 PDFs recebidos conferidos na suíte. Transcrição histórica separada dos parâmetros demonstrativos.

**Não validados:** deploy real no Railway, conexão ao projeto Neon do usuário, valores oficiais de 2026, conferência com contracheques, casos especiais listados no README e restauração deste ambiente em uma nova tarefa. A integração PostgreSQL local demonstra a compatibilidade do driver/schema com o protocolo usado pelo Neon; não comprova acesso a uma conta Neon específica.

O app está preparado para desenvolvimento e demonstração; a liberação como simulador oficial depende de dados auditados e das rotinas especiais ainda pendentes. Os arquivos Docker/Railway não constituem uma implantação realizada.

## Inclusão dos dados remuneratórios reais de 2026

- Suíte ampliada: **72 testes aprovados**, incluindo as 50 posições reais, valores publicados de cada família de cargo/função, hashes das nove fontes preservadas, quota de 50% da pontuação GDPI, GTE paga integralmente, pré-requisitos e exportações sem líquido fictício.
- Teste funcional em Chromium nas larguras de 1440 e 390 pixels: abertura em Reais · bruto, seleção de FGD, combinação DAD/GTED, comparação bruta, catálogo completo, cenários salvos/editados, fluxos demonstrativos, carreira, fontes e exportação. Sem erros JavaScript ou overflow horizontal nesses fluxos.
- Inicialização repetida do banco local preservou o catálogo real e as versões existentes. O novo catálogo fica em tabela própria e não promove as fixtures demonstrativas a parâmetros de folha.
- Carga reproduzida das cópias oficiais com `scripts/build_career_data.py`, hashes conferidos e validação do contrato `CareerData`.
- `docker build --check .`, compilação Python e checagem de sintaxe JavaScript aprovados nesta etapa. Não foi executado novo deploy real no Railway nem conexão a uma conta Neon específica.

O modo real apura bruto e projeções brutas, com descontos e líquido nulos. A opção A de comissão real permanece não habilitada até conferir a manutenção das parcelas no enquadramento. Esses limites são visíveis na interface e nos resultados exportados.
