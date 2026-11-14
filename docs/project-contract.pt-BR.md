[🇺🇸 English](project-contract.md) · 🇧🇷 Português

# O que o seu projeto precisa

O Deproi funciona com qualquer stack que rode no Docker Compose. O seu projeto precisa de cinco coisas. O [exemplo](../example/) tem todas elas.

## 1. Um Dockerfile, e um healthcheck no serviço web

O healthcheck é como o Deproi distingue uma versão quebrada de uma saudável. Sem ele, o deploy é recusado.

Ou no Dockerfile:

```dockerfile
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
  CMD ["curl", "-fsS", "http://127.0.0.1:8000/health"]
```

ou no `compose.yaml`:

```yaml
services:
  web-prod:
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/health"]
      interval: 5s
      timeout: 3s
      start_period: 10s
      retries: 3
```

Faça o endpoint verificar o que importa (o app responde, ele alcança o banco de dados) e mantenha-o rápido. O `curl` precisa existir na imagem; se não existir, use um script pequeno na sua linguagem.

Os contêineres também devem parar rápido quando o Docker envia `SIGTERM`. Se o seu processo roda como PID 1 e ignora o sinal (comum com Python ou Node puros), cada recriação espera o timeout de 10 segundos do Docker: adicione `init: true` ao serviço.

## 2. Imagens construídas com a tag `${DEPROI_TAG}`

O Deproi define `DEPROI_TAG` como o commit (12 caracteres hexadecimais) quando constrói e recria. A reversão e a limpeza encontram as versões por essa tag.

```yaml
services:
  web-prod:
    build: .
    image: myapp:${DEPROI_TAG:-local}
```

Todo serviço com `build:` precisa usar `image: <compose.image>:${DEPROI_TAG}`. Serviços que reaproveitam a sua imagem (workers) devem usar a mesma tag. Imagens de terceiros (`postgres:16`, `redis:7`) mantêm as próprias tags.

## 3. Um perfil e um sufixo por ambiente

Se vários ambientes (ou apps) dividem um servidor, todo serviço de um ambiente leva o perfil dele e um sufixo no nome:

```yaml
services:
  web-prod:
    profiles: [prod]
  worker-prod:
    profiles: [prod]
  web-test:
    profiles: [test]
```

Com `compose.service_suffix: "-prod"`, o Deproi recusa uma definição em que um serviço sem o sufixo subiria: um serviço sem `profiles:` fica ativo em **todos** os perfis e acabaria em todos os projetos.

Um servidor com um único ambiente pode dispensar perfis e sufixo.

## 4. Um arquivo env versionado (recomendado)

`deploy/prod.compose.env`, commitado, com valores não secretos:

```bash
COMPOSE_PROJECT_NAME=myapp-prod
DEPROI_TAG=local
WEB_PORT=8080
```

Quando `compose.env_file` está definido, o Deproi lê esse arquivo **do commit buscado, antes de mover o checkout**, e recusa o deploy se o `COMPOSE_PROJECT_NAME` não for o projeto configurado. Um commit não consegue desviar o deploy para outro projeto.

Os segredos ficam em `/etc/deproi/<name>.secrets.env` no servidor (root `0600`), que o Deproi passa depois desse arquivo.

## 5. Uma cópia do `deproi.py`

Faça o commit do `deproi.py` no seu projeto, por padrão como `deploy/deproi.py`. O servidor o instala uma vez e, daí em diante, cada deploy se atualiza a partir do commit. Para atualizar a versão, substitua o arquivo (ou faça o merge do pull request que o `deproi-update.yml` abre).

## Checklist

- [ ] O serviço web tem um healthcheck que falha quando o app está quebrado.
- [ ] Os serviços construídos usam `image: <image>:${DEPROI_TAG:-local}`.
- [ ] Os serviços de cada ambiente têm o perfil e o sufixo dele (se o servidor for compartilhado).
- [ ] `deploy/<env>.compose.env` tem `COMPOSE_PROJECT_NAME`.
- [ ] Nenhum segredo no repositório; eles ficam em `/etc/deproi/<name>.secrets.env`.
- [ ] `deploy/deproi.py` está commitado.
- [ ] As migrations mantêm a versão anterior funcionando (expanda agora, contraia num deploy posterior): a reversão não as desfaz.
- [ ] `docker compose --env-file deploy/<env>.compose.env --profile <env> config` funciona na sua máquina.

Exemplos por stack: [receitas](recipes.pt-BR.md).
