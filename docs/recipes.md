🇺🇸 English · [🇧🇷 Português](recipes.pt-BR.md)

# Recipes

Hooks and health checks for common stacks. Every command is a list of arguments and runs on the new image (`docker compose run --rm --no-deps <service> …`).

## Django

```json
"hooks": {
  "pre_migrate": [{ "name": "check", "command": ["python", "manage.py", "check", "--deploy", "--fail-level", "ERROR"] }],
  "migrate": [{ "name": "migrate", "command": ["python", "manage.py", "migrate", "--noinput"] }],
  "post_migrate": [{ "name": "static", "command": ["python", "manage.py", "collectstatic", "--noinput"] }]
}
```

Health endpoint: a view that returns 200 after a cheap database query. If static files live in a volume shared with the web container, collect them in `post_migrate`; if they are baked into the image, skip it.

## Ruby on Rails

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["bin/rails", "db:migrate"] }]
}
```

Rails 7.1+ ships `/up` as a health endpoint: `test: ["CMD", "curl", "-fsS", "http://127.0.0.1:3000/up"]`.

## Laravel

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["php", "artisan", "migrate", "--force"] }],
  "post_migrate": [
    { "name": "config", "command": ["php", "artisan", "config:cache"] },
    { "name": "routes", "command": ["php", "artisan", "route:cache"] }
  ]
}
```

Laravel 11+ ships `/up`.

## Node.js with Prisma

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["npx", "prisma", "migrate", "deploy"] }]
}
```

Make sure the Prisma CLI is in the production image (or use a dedicated `migrate` service whose image has it, with `"service": "migrate-prod"`).

## Node.js with a queue worker

```json
"protected_services": [{
  "service": "worker-prod",
  "busy_check": ["test", "!", "-e", "/tmp/working"],
  "quiesce": ["touch", "/tmp/paused"],
  "resume": ["rm", "-f", "/tmp/paused"]
}]
```

The worker writes `/tmp/working` while it processes a job and stops taking new jobs while `/tmp/paused` exists. Health check without `curl` in `node:*-slim`:

```yaml
healthcheck:
  test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3000/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
```

Run `node` directly (`CMD ["node", "src/server.js"]`) rather than through `npm start`, so `SIGTERM` reaches your process.

## Go, Rust, or any binary

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["/app/server", "migrate"] }]
}
```

Minimal images often have no `curl`: build a `healthcheck` subcommand into the binary (`CMD ["/app/server", "healthcheck"]`).

## Static site behind nginx

No hooks. Health check: `test: ["CMD", "wget", "-qO-", "http://127.0.0.1/"]` (nginx:alpine has `wget`). Pair it with the [Cloudflare purge](integrations.md#cloudflare).

## A queue worker with long jobs (Celery, Sidekiq, RQ…)

Make it a protected service so a deploy never kills a running job:

```json
"protected_services": [{
  "service": "worker-prod",
  "busy_check": ["python", "-m", "myapp.worker_busy"],
  "quiesce": ["celery", "-A", "myapp", "control", "cancel_consumer", "long-jobs"],
  "resume": ["celery", "-A", "myapp", "control", "add_consumer", "long-jobs"]
}]
```

`busy_check` exits `1` while a job runs (for Celery, `celery inspect active` filtered for this worker), `0` when idle. With `quiesce`, the worker stops taking new jobs, `busy_check` runs once more, and only then is it recreated. A busy worker stays on its version and updates on the next deploy.

## A refusing guard

To stop deploys that carry a migration needing manual work, write a command that exits non-zero when one is pending, and refuse:

```json
"pre_migrate": [{ "name": "manual-migrations", "command": ["python", "manage.py", "check_manual_migrations"], "on_failure": "refuse" }]
```

The deploy ends `REFUSED` before any migration runs and before any service is touched.

## Several environments on one server

```text
/usr/local/sbin/deproi-myapp-test   →  /etc/deproi/myapp-test.json  →  branch develop, project myapp-test, suffix -test
/usr/local/sbin/deproi-myapp-prod   →  /etc/deproi/myapp-prod.json  →  branch main,    project myapp-prod, suffix -prod
```

Two checkouts, two configs, two keys, two sudo rules, two workflows. Use different `compose.image` names (`myapp-test`, `myapp`) so the cleanup of one never sees the images of the other, and different published ports (`WEB_PORT=3001` / `3000` in each env file). Each workflow file must be merged into the branch it deploys.
