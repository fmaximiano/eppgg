# Validação desta implementação

Executada no ambiente de desenvolvimento, em 23/10/2026:

- Suíte: `.venv/bin/python -m pytest -q` — **61 passed**. Um aviso de depreciação de dependência no TestClient; nenhuma falha.
- `tests/browser_smoke.py` — passou em Chromium, larguras de 1440 e 390 pixels. Fluxos de cálculo, GDPI abaixo do mínimo, cenários salvos/editados, comparação, evolução simples, fontes, download e bloqueio sem tabelas oficiais. Sem erros JavaScript ou overflow horizontal nesses fluxos.
- `tests/postgres_smoke.py` — passou em PostgreSQL 17 descartável com TLS: criação de schema, importação idempotente, persistência entre instâncias e cálculo HTTP. Conexão criptografada confirmada em `pg_stat_ssl`. Recursos de teste removidos ao terminar.
- Imagem Docker construída com dependências travadas e hashes verificados. Foi necessário fornecer a CA confiável do proxy como segredo BuildKit para o build neste ambiente. Nenhuma verificação de certificado ou checksum foi desativada.
- Imagem executada como usuário não root, usando `PORT=9070`; `/health` e `/api/calculate` responderam corretamente. O teste inicial encontrou permissões restritas nos arquivos copiados; corrigido com leitura explícita para o usuário da imagem e revalidado.
- `node --check app/static/app.js` e compilação Python passaram.
- Checksums dos 11 PDFs recebidos conferidos na suíte. Transcrição histórica separada dos parâmetros demonstrativos.

**Não validados:** deploy real no Railway, conexão ao projeto Neon do usuário, valores oficiais de 2026, conferência com contracheques, casos especiais listados no README e restauração deste ambiente em uma nova tarefa. A integração PostgreSQL local demonstra a compatibilidade do driver/schema com o protocolo usado pelo Neon; não comprova acesso a uma conta Neon específica.

O app está preparado para desenvolvimento e demonstração; a liberação como simulador oficial depende de dados auditados e das rotinas especiais ainda pendentes. Os arquivos Docker/Railway não constituem uma implantação realizada.
