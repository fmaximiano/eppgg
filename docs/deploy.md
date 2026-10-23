# Railway + Neon

## Preparação

O repositório contém `Dockerfile` e `railway.toml`. Não foi publicado automaticamente em contas externas. A imagem executa como usuário sem privilégios, respeita `PORT` e verifica o serviço em `/health`, incluindo acesso ao banco.

1. Envie os arquivos deste projeto ao seu repositório GitHub.
2. No Neon, crie um projeto e um banco PostgreSQL. Use a connection string recomendada pelo painel (pooled ou direct), com TLS habilitado.
3. No Railway, crie um serviço a partir desse repositório. O builder Docker e o healthcheck já estão em `railway.toml`.
4. Nas **Variables** do Railway, adicione `DATABASE_URL` com a connection string do Neon. Insira a credencial somente nesse campo seguro. Não coloque no código, no Dockerfile, no terminal com saída gravada ou em arquivos versionados.
5. Implante o serviço e confira o healthcheck. O processo cria `parameter_sets` e `career_data_sets` e carrega o conjunto demonstrativo e os dados remuneratórios e a folha real de 2026 se ainda não existirem. A v2 substitui explicitamente a v1, preservando seu histórico e os conjuntos administrativos distintos. A carga real vem no repositório; não depende de executar um comando administrativo depois do deploy. Gere o domínio público pelo painel do Railway.
6. Confira fontes, regime e líquido com contracheques. A folha de 2026 já vem incluída; para outros períodos, importe novas versões por sessão administrativa. Uma versão administrativa com vigência sobreposta é preservada, sem substituição pela carga padrão.

O usuário de banco precisa inicialmente criar a tabela; após a inicialização, pode ter permissões limitadas a leitura e à inserção idempotente do demo. Alterações futuras de schema deverão ser tratadas em migrações, não por exclusão de tabelas. `create_all` apenas cria tabelas ausentes e não migra schema existente.

Não use o SQLite efêmero da imagem como persistência em produção: substitua o `DATABASE_URL` de fallback pelo Neon antes de publicar. A conexão não valida o enquadramento individual: configure regime, adesão, família e rubricas de cada cenário.

## Testar a imagem

```bash
docker build -t eppgg .
docker run --rm -p 8000:8000 eppgg
```

Para validar o Neon na imagem, injete `DATABASE_URL` do seu gerenciador de segredos, sem imprimi-lo:

```bash
docker run --rm -p 8000:8000 --env DATABASE_URL eppgg
```

O Dockerfile usa instruções convencionais, sem mounts de segredo, para ser compatível com o construtor do Railway. A instalação mantém a verificação de TLS e dos hashes das dependências. Em ambientes corporativos com inspeção TLS, configure a cadeia CA confiável no construtor utilizado; não desative a verificação de certificados ou checksums. O build do Railway com acesso direto confiável ao PyPI não precisa dessa configuração corporativa.

## Dados e privacidade

O Neon armazena conjuntos de parâmetros legais versionados. Cenários pessoais ficam no navegador; não há sincronização entre dispositivos. Não são pedidos nome de beneficiário, CPF ou contracheque. A API recebe as entradas estritamente necessárias à simulação e não registra os corpos de requisição. Não habilite logging de corpos ou URLs de conexão no deploy. Faça backup do banco antes de operações administrativas.

## Diagnóstico

- Falha de conexão: confira host, banco, credencial, acesso de rede e TLS do Neon nas configurações, sem expor a URL em logs.
- `/health` retorna 503 quando não consegue consultar o banco.
- Ausência de tabela oficial retorna 422 explicativo; não há fallback silencioso para valores demonstrativos.
- Importação com mesma versão e conteúdo é idempotente; conteúdo diferente requer outra versão. Sobreposição no mesmo status é rejeitada.
- Variáveis de serviços externos não são necessárias para o desenvolvimento local; não é preciso token do Railway para executar o app.
