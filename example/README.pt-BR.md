[🇺🇸 English](README.md) · 🇧🇷 Português

# Exemplo do Deproi

Um projeto mínimo que segue o [contrato do projeto](../docs/project-contract.pt-BR.md): um serviço web com healthcheck, uma "migration" e um worker de longa duração. O teste de ponta a ponta do Deproi faz o deploy dele de verdade; copie-o como ponto de partida.

| Arquivo | O que mostra |
|---|---|
| [`Dockerfile`](Dockerfile) | `HEALTHCHECK` no serviço web. |
| [`compose.yaml`](compose.yaml) | Perfil `prod`, sufixo `-prod`, `image: deproi-example:${DEPROI_TAG}`. |
| [`deploy/prod.compose.env`](deploy/prod.compose.env) | `COMPOSE_PROJECT_NAME` e outros valores que não são segredo. |
| [`deploy/server-config.json`](deploy/server-config.json) | A configuração do servidor: `/etc/deproi/deproi-example-prod.json`. |
| [`app/server.py`](app/server.py) | `/health` para o healthcheck; `/` mostra a versão e o schema. |
| [`app/migrate.py`](app/migrate.py) | O gancho `migrate`: roda na imagem nova antes da recriação. |
| [`app/worker.py`](app/worker.py) | Um serviço protegido: `--busy` sai com 1 enquanto um job roda. |

## Teste localmente (sem o Deproi)

```bash
cd example
DEPROI_TAG=dev docker compose --env-file deploy/prod.compose.env --profile prod up -d --build
curl http://127.0.0.1:8080/
docker compose --env-file deploy/prod.compose.env --profile prod down -v
```

## Quebre de propósito

Faça commit de um arquivo vazio `app/BROKEN`: o `/health` dessa versão devolve 500, ela nunca fica saudável e o Deproi reverte para a anterior (`FAILED_ROLLED_BACK`). Remova o arquivo e o próximo deploy entra no ar.

## Veja o deploy de ponta a ponta

Na raiz do repositório, com o Docker rodando:

```bash
tests/e2e/run.sh
```

Um contêiner faz o papel do servidor; o script roda o `prepare-server.sh` e depois faz o deploy deste exemplo por SSH, com uma chave restrita: sucesso, um commit novo, um commit quebrado e sua reversão, um worker ocupado, a autoatualização e as recusas.
