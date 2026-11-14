🇺🇸 English · [🇧🇷 Português](README.pt-BR.md)

# Deproi example

A tiny project that follows the [project contract](../docs/project-contract.md): a web service with a health check, a "migration" and a long-running worker. Deproi's end-to-end test deploys it for real; copy it as a starting point.

| File | What it shows |
|---|---|
| [`Dockerfile`](Dockerfile) | `HEALTHCHECK` on the web service. |
| [`compose.yaml`](compose.yaml) | Profile `prod`, suffix `-prod`, `image: deproi-example:${DEPROI_TAG}`. |
| [`deploy/prod.compose.env`](deploy/prod.compose.env) | `COMPOSE_PROJECT_NAME` and other non-secret values. |
| [`deploy/server-config.json`](deploy/server-config.json) | The server config: `/etc/deproi/deproi-example-prod.json`. |
| [`app/server.py`](app/server.py) | `/health` for the health check; `/` shows the version and schema. |
| [`app/migrate.py`](app/migrate.py) | The `migrate` hook: runs on the new image before recreating. |
| [`app/worker.py`](app/worker.py) | A protected service: `--busy` exits 1 while a job runs. |

## Try it locally (without Deproi)

```bash
cd example
DEPROI_TAG=dev docker compose --env-file deploy/prod.compose.env --profile prod up -d --build
curl http://127.0.0.1:8080/
docker compose --env-file deploy/prod.compose.env --profile prod down -v
```

## Break it on purpose

Commit an empty file `app/BROKEN`: that version's `/health` returns 500, it never becomes healthy, and Deproi rolls back to the previous one (`FAILED_ROLLED_BACK`). Remove the file and the next deploy goes live.

## See it deployed end to end

From the repository root, with Docker running:

```bash
tests/e2e/run.sh
```

A container plays the server; the script runs `prepare-server.sh`, then deploys this example over SSH with a locked key: success, a new commit, a broken commit and its rollback, a busy worker, the self-update and the refusals.
