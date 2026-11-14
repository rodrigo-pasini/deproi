🇺🇸 English · [🇧🇷 Português](project-contract.pt-BR.md)

# What your project needs

Deproi works with any stack that runs in Docker Compose. Your project needs five things. The [example](../example/) has all of them.

Deproi reads `compose.yaml` by default. If your file is `docker-compose.yml` (or there are several), list them in `compose.files` in the [configuration](configuration.md#compose).

## 1. A Dockerfile, and a health check on the web service

The health check is how Deproi tells a broken version from a healthy one. Without it, the deploy is refused.

Either in the Dockerfile:

```dockerfile
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
  CMD ["curl", "-fsS", "http://127.0.0.1:8000/health"]
```

or in `compose.yaml`:

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

Make the endpoint check what matters (the app answers, it reaches the database) and keep it fast. `curl` must exist in the image, or use a tiny script in your language instead.

Containers should also stop quickly when Docker sends `SIGTERM`. If your process runs as PID 1 and ignores it (common with plain Python or Node), every recreate waits Docker's 10-second timeout: add `init: true` to the service.

## 2. Built images tagged with `${DEPROI_TAG}`

Deproi sets `DEPROI_TAG` to the commit (12 hex characters) when it builds and recreates. Rollback and cleanup find versions by that tag.

```yaml
services:
  web-prod:
    build: .
    image: myapp:${DEPROI_TAG:-local}
```

Every service with `build:` must use `image: <compose.image>:${DEPROI_TAG}`. Services that reuse your image (workers) should use the same tag. Third-party images (`postgres:16`, `redis:7`) keep their own tags.

Deproi sets `DEPROI_TAG` in the process environment, which wins over any value in an env file: `DEPROI_TAG=local` in the env file is only the default for running the project by hand.

Services that use your image are "the project's own" and are recreated on every deploy. Third-party services (a database, a cache) are started before the hooks if they are not running, and are only recreated when their definition changes.

## 3. A profile and a suffix per environment

If several environments (or apps) share a server, every service of an environment carries its profile and a name suffix:

```yaml
services:
  web-prod:
    profiles: [prod]
  worker-prod:
    profiles: [prod]
  web-test:
    profiles: [test]
```

With `compose.service_suffix: "-prod"`, Deproi refuses a definition where a service without the suffix would start: a service without `profiles:` is active in **every** profile and would end up in every project.

A server with a single environment can skip profiles and the suffix.

On a shared server, each environment also needs its **own published ports** (for example `${WEB_PORT}` in the env file: 3000 for production, 3001 for staging) and its **own image name** (`compose.image`: `myapp` and `myapp-staging`), so the cleanup of one never removes the other's previous image.

With profiles on every service, a plain `docker compose up` starts nothing: run the project by hand with `docker compose --env-file deploy/prod.compose.env --profile prod up`.

## 4. A versioned env file (recommended)

`deploy/prod.compose.env`, committed, with non-secret values:

```bash
COMPOSE_PROJECT_NAME=myapp-prod
DEPROI_TAG=local
WEB_PORT=8080
```

When `compose.env_file` is set, Deproi reads this file **from the fetched commit, before moving the checkout**, and refuses if `COMPOSE_PROJECT_NAME` is not the configured project. A commit cannot redirect the deploy to another project.

Secrets go in `/etc/deproi/<name>.secrets.env` on the server (root `0600`), which Deproi passes after this file.

## 5. A copy of `deproi.py`

Commit `deproi.py` to your project, by default as `deploy/deproi.py`. The server installs it once, and from then on each deploy updates itself from the commit. To upgrade, replace the file (or merge the pull request `deproi-update.yml` opens).

## Checklist

- [ ] The web service has a health check that fails when the app is broken.
- [ ] Built services use `image: <image>:${DEPROI_TAG:-local}`.
- [ ] Each environment's services have its profile and suffix (if the server is shared).
- [ ] `deploy/<env>.compose.env` has `COMPOSE_PROJECT_NAME`.
- [ ] No secrets in the repository; they go in `/etc/deproi/<name>.secrets.env`.
- [ ] `deploy/deproi.py` is committed.
- [ ] Migrations keep the previous version working (expand now, contract in a later deploy): a rollback does not undo them.
- [ ] Services have `restart: unless-stopped` (Deproi never starts a stopped protected service by itself), and stop quickly on `SIGTERM` (`init: true` if needed).
- [ ] On a shared server: different published ports and image names per environment.
- [ ] `compose.files` lists your compose file if it is not `compose.yaml`.
- [ ] `docker compose --env-file deploy/<env>.compose.env --profile <env> config` works on your machine.

Stack-specific examples: [recipes](recipes.md).
