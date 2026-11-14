[🇺🇸 English](recipes.md) · 🇧🇷 Português

# Receitas

Ganchos e healthchecks para stacks comuns. Cada comando é uma lista de argumentos e roda na imagem nova (`docker compose run --rm --no-deps <service> …`).

## Django

```json
"hooks": {
  "pre_migrate": [{ "name": "check", "command": ["python", "manage.py", "check", "--deploy", "--fail-level", "ERROR"] }],
  "migrate": [{ "name": "migrate", "command": ["python", "manage.py", "migrate", "--noinput"] }],
  "post_migrate": [{ "name": "static", "command": ["python", "manage.py", "collectstatic", "--noinput"] }]
}
```

Endpoint de saúde: uma view que devolve 200 depois de uma consulta barata ao banco. Se os arquivos estáticos ficam num volume compartilhado com o contêiner web, colete-os no `post_migrate`; se já vêm dentro da imagem, pule esse passo.

## Ruby on Rails

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["bin/rails", "db:migrate"] }]
}
```

O Rails 7.1+ já traz `/up` como endpoint de saúde: `test: ["CMD", "curl", "-fsS", "http://127.0.0.1:3000/up"]`.

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

O Laravel 11+ já traz `/up`.

## Node.js com Prisma

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["npx", "prisma", "migrate", "deploy"] }]
}
```

Garanta que a CLI do Prisma esteja na imagem de produção (ou use um serviço `migrate` dedicado, cuja imagem a tenha, com `"service": "migrate-prod"`).

## Node.js com um worker de fila

```json
"protected_services": [{
  "service": "worker-prod",
  "busy_check": ["test", "!", "-e", "/tmp/working"],
  "quiesce": ["touch", "/tmp/paused"],
  "resume": ["rm", "-f", "/tmp/paused"]
}]
```

O worker escreve `/tmp/working` enquanto processa uma tarefa e para de pegar tarefas novas enquanto `/tmp/paused` existir. Healthcheck sem `curl` no `node:*-slim`:

```yaml
healthcheck:
  test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3000/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
```

Rode o `node` diretamente (`CMD ["node", "src/server.js"]`) em vez de passar pelo `npm start`, para que o `SIGTERM` chegue ao seu processo.

## Go, Rust ou qualquer binário

```json
"hooks": {
  "migrate": [{ "name": "migrate", "command": ["/app/server", "migrate"] }]
}
```

Imagens mínimas muitas vezes não têm `curl`: inclua um subcomando `healthcheck` no binário (`CMD ["/app/server", "healthcheck"]`).

## Site estático atrás do nginx

Sem ganchos. Healthcheck: `test: ["CMD", "wget", "-qO-", "http://127.0.0.1/"]` (o nginx:alpine tem `wget`). Combine com a [purga do Cloudflare](integrations.pt-BR.md#cloudflare).

## Um worker de fila com jobs longos (Celery, Sidekiq, RQ…)

Faça dele um serviço protegido, para que um deploy nunca mate um job em andamento:

```json
"protected_services": [{
  "service": "worker-prod",
  "busy_check": ["python", "-m", "myapp.worker_busy"],
  "quiesce": ["celery", "-A", "myapp", "control", "cancel_consumer", "long-jobs"],
  "resume": ["celery", "-A", "myapp", "control", "add_consumer", "long-jobs"]
}]
```

O `busy_check` sai com `1` enquanto um job roda (no Celery, `celery inspect active` filtrado para este worker) e com `0` quando está livre. Com `quiesce`, o worker para de pegar jobs novos, o `busy_check` roda mais uma vez e só então ele é recriado. Um worker ocupado fica na versão dele e atualiza no próximo deploy.

## Uma guarda que recusa

Para barrar deploys que trazem uma migration que exige trabalho manual, escreva um comando que saia com código diferente de zero quando houver uma pendente, e recuse:

```json
"pre_migrate": [{ "name": "manual-migrations", "command": ["python", "manage.py", "check_manual_migrations"], "on_failure": "refuse" }]
```

O deploy termina em `REFUSED` antes de qualquer migration rodar e antes de qualquer serviço ser tocado.

## Vários ambientes num servidor

```text
/usr/local/sbin/deproi-myapp-test   →  /etc/deproi/myapp-test.json  →  branch develop, project myapp-test, suffix -test
/usr/local/sbin/deproi-myapp-prod   →  /etc/deproi/myapp-prod.json  →  branch main,    project myapp-prod, suffix -prod
```

Dois checkouts, duas configurações, duas chaves, duas regras do sudo, dois workflows. Use nomes diferentes em `compose.image` (`myapp-test`, `myapp`) para que a limpeza de um nunca enxergue as imagens do outro, e portas publicadas diferentes (`WEB_PORT=3001` / `3000` em cada arquivo env). Cada arquivo de workflow precisa chegar, por merge, à branch que ele implanta.
