🇺🇸 English · [🇧🇷 Português](configuration.pt-BR.md)

# Configuration reference

Each environment has one file on the server: **`/etc/deproi/<name>.json`**, read by **`/usr/local/sbin/deproi-<name>`**. The installed command's name picks the file, and the file's `name` must match it. Nothing in the repository, the SSH connection or the environment variables can point Deproi somewhere else.

- **Owner and mode:** `root:root`, not writable by group or others (`0600` recommended). The folder `/etc/deproi` must not be writable by others either. Deproi refuses to run otherwise.
- **Strict:** an unknown key is an error that names the key (`unknown key compose.profile`). A typo never switches a protection off silently.
- **Safe defaults:** every optional key has a default. A newer Deproi keeps working with an older file.
- **Editor support:** keep the `$schema` line and VS Code (and most editors) will autocomplete and validate against [`deproi.schema.json`](../deproi.schema.json). It is only read by your editor; pin it to your version's tag if you prefer.
- **No secrets here.** Tokens and passwords go in separate root-only files (`0600`) that this file points to.

## A complete example

```json
{
  "$schema": "https://raw.githubusercontent.com/rodrigo-pasini/deproi/main/deproi.schema.json",
  "name": "myapp-prod",
  "language": "en",
  "checkout": { "path": "/srv/myapp-prod", "owner": "ubuntu", "branch": "main" },
  "compose": {
    "project": "myapp-prod",
    "env_file": "deploy/prod.compose.env",
    "secrets_file": "/etc/deproi/myapp-prod.secrets.env",
    "profiles": ["prod"],
    "service_suffix": "-prod",
    "web_service": "web-prod",
    "image": "myapp"
  },
  "url": "https://app.example.com",
  "docs": "https://github.com/acme/myapp/blob/main/docs/deploy.md",
  "hooks": {
    "pre_migrate": [{ "name": "check", "command": ["python", "manage.py", "check", "--deploy"] }],
    "migrate": [{ "name": "migrate", "command": ["python", "manage.py", "migrate", "--noinput"] }]
  },
  "protected_services": [
    { "service": "worker-prod", "busy_check": ["python", "worker.py", "--busy"] }
  ],
  "integrations": {
    "cloudflare": { "credentials_file": "/etc/deproi/myapp-prod.cloudflare.env", "zone_id": "0123456789abcdef0123456789abcdef" }
  }
}
```

## Top level

| Key | Required | Default | What it does |
|---|---|---|---|
| `name` | ✅ | — | Must equal `<name>` of `/usr/local/sbin/deproi-<name>`. Lowercase letters, digits and `-`. |
| `language` | | `"en"` | Language of the messages for people: `"en"` or `"pt-BR"`. The `result:` line is always English. |
| `checkout` | ✅ | — | The git checkout on the server. [Details](#checkout). |
| `compose` | ✅ | — | The Docker Compose project. [Details](#compose). |
| `url` | | none | Public address, shown in the success message and used as the default host for the Cloudflare purge. |
| `script_path` | | `"deploy/deproi.py"` | Where the project keeps its copy of `deproi.py`. The self-update reads it from each commit. |
| `docs` | | Deproi's [operations guide](operations.md) | Link shown in failure messages: point it to your own plan B. |
| `timeouts` | | see below | [Details](#timeouts). |
| `build` | | see below | [Details](#build). |
| `health_interval` | | `5` | Seconds between two health checks. |
| `min_free_disk_gb` | | `5` | Below this much free space in `/var/lib/docker`, the deploy stops before touching anything. |
| `hooks` | | none | Commands at fixed points of the deploy. [Details](#hooks). |
| `protected_services` | | none | Services that must not be recreated while busy. [Details](#protected-services). |
| `integrations` | | none | Better Stack, Cloudflare, webhook. [Details](integrations.md). |
| `config_version` | | `1` | Format version of this file. |

## checkout

| Key | Required | Default | What it does |
|---|---|---|---|
| `path` | ✅ | — | Absolute path of the checkout, e.g. `/srv/myapp-prod`. |
| `owner` | ✅ | — | The user that owns the checkout. Git runs as this user, never as root. Cannot be `root`. |
| `branch` | ✅ | — | The branch this environment publishes. The checkout must be on it. |
| `remote` | | `"origin"` | The git remote to fetch from. |

Deproi only moves the checkout forward (`git merge --ff-only`). It never runs `reset`, `clean`, `stash` or `checkout`, so untracked files (secrets, backups) are safe. A checkout with local changes to tracked files, or with commits the remote does not have, is refused.

## compose

| Key | Required | Default | What it does |
|---|---|---|---|
| `project` | ✅ | — | Compose project name. Always passed with `--project-name`, so no file can redirect the deploy to another project. |
| `web_service` | ✅ | — | The service whose health check decides between success and rollback. |
| `image` | ✅ | — | Image repository, **without tag**. Every built service must use `image: <image>:${DEPROI_TAG}`. |
| `files` | | `["compose.yaml"]` | Compose files, relative to the checkout. |
| `env_file` | | none | Versioned env file (non-secret values). When set, its `COMPOSE_PROJECT_NAME` must equal `project`; Deproi checks it in the fetched commit **before** moving the checkout. |
| `secrets_file` | | none | Untracked env file with secrets, passed after `env_file` so its values win. Absolute (recommended: `/etc/deproi/<name>.secrets.env`, root `0600`) or relative to the checkout. |
| `profiles` | | none | Compose profiles of this environment. |
| `service_suffix` | | none | When set, **every** service of the definition must end with it (for example `-prod`). This fence stops a service without `profiles:` from starting in every environment of the same server. |
| `tag_variables` | | `["DEPROI_TAG"]` | Variables set to the commit tag (12 hex characters) when Compose interpolates the files. Add more if your compose file uses other names (for example a release variable for telemetry). |

## timeouts

All in seconds.

| Key | Default | What it limits |
|---|---|---|
| `lock` | `1800` | Waiting for another deploy of the same environment to finish. |
| `build` | `2400` | `docker compose build`. |
| `migrations` | `2400` | All `migrate` hooks together. |
| `health` | `240` | Waiting for the web service to become healthy (and again after a rollback). The wait also ends early when Docker reports `unhealthy` three times in a row. Fast-starting apps can lower it. |
| `hook` | `600` | Each `pre_migrate` / `post_migrate` hook without its own `timeout`. |
| `post_deploy` | `300` | Each `post_deploy` hook without its own `timeout`. |

## build

| Key | Default | What it does |
|---|---|---|
| `low_priority` | `true` | Builds with `nice -n 10 ionice -c3`, so the app keeps serving while the image builds. |
| `pull` | `false` | Adds `--pull` (always fetch newer base images). |

## hooks

A hook is a command that runs **on the new image**, through `docker compose run --rm --no-deps <service> <command…>`, before the services are recreated. The command is a list of arguments, never a shell string.

Third-party services (a database, a cache: anything not running your image) are started first, if they are not running yet, and Deproi waits for them to be healthy. So migrations work on the very first deploy too. Give your database a `healthcheck:` (for Postgres, `pg_isready`) so "started" means "ready".

| Point | When | Default on failure |
|---|---|---|
| `pre_migrate` | After the build, before anything changes. For checks: framework deploy checks, a guard that refuses risky migrations. | `fail` |
| `migrate` | Database migrations. All `migrate` hooks share `timeouts.migrations`. | `fail` |
| `post_migrate` | After migrations, before recreating: cache warm-up, syncing feature flags… | `warn` |
| `post_deploy` | In the background, after the new version is live. Never changes the outcome; the next deploy shows its result. | `warn` (only option) |

Each hook:

| Key | Required | What it does |
|---|---|---|
| `name` | ✅ | Short id shown in the log: lowercase letters, digits, `-`, `_`. Unique per point. |
| `command` | ✅ | The command, as a list: `["python", "manage.py", "migrate"]`. |
| `service` | | Which service's image runs it. Default: `compose.web_service`. |
| `env` | | Extra environment variables: `{"COLLECTSTATIC": "0"}`. |
| `timeout` | | Seconds, overriding the default for this hook. |
| `on_failure` | | `fail` → `FAILED_NO_CHANGE` (exit 3) · `refuse` → `REFUSED` (exit 2) · `warn` → log it and continue. |

> Migrations are not undone by a rollback. Write them so the previous version still works with the new schema (expand first, contract in a later deploy).

## protected services

For services that must not be stopped in the middle of their work, such as a queue worker running a long job.

| Key | Required | What it does |
|---|---|---|
| `service` | ✅ | The Compose service. Cannot be the web service. |
| `busy_check` | ✅ | Runs with `docker exec` in its container. Exit `0` = idle, `1` = busy, anything else = no answer (treated as busy). |
| `quiesce` | | Optional: tells it to stop taking new work. `busy_check` runs again right after, so nothing slips in between. |
| `resume` | | Optional: undoes `quiesce` when the service ends up not recreated. |

`busy_check`, `quiesce` and `resume` are lists of arguments run with `docker exec`, without a shell: use programs that exist in the image (`["test", "!", "-e", "/tmp/working"]`, `["touch", "/tmp/paused"]`, `["node", "busy.js"]`).

What happens to each protected service:

| State | What Deproi does | In the `result:` line |
|---|---|---|
| No container yet | Creates it with the rest | `updated` |
| Container exists but stopped | Leaves it alone (someone stopped it on purpose) | `stopped` |
| Busy, or no answer | Keeps it on the previous version; the deploy is `SUCCESS_PROTECTED_DEFERRED` | `deferred` |
| Idle | Recreates it after the other services | `updated` |

Good to know:

- **Order:** the other services are recreated first, then the idle protected ones. Use `quiesce` (and check again) so no job starts in between.
- **Rollback:** an idle protected service that was updated goes back with the rest (`rolled_back`); a busy one stays on the new version.
- **Graceful stop:** handle `SIGTERM` by finishing the current job, and set `stop_grace_period` in compose to the longest job. That also covers the rare race between the busy check and the recreate.
- **Restart policy:** give it `restart: unless-stopped`. A protected service whose container exists but is stopped is never started by Deproi (someone may have stopped it on purpose), so one that crashed without a restart policy would stay down.
- **Always busy:** a worker that is never idle never updates. Drain the queue, or run the deploy again from Actions when it is idle.

## Files next to the config

| File | Mode | Holds |
|---|---|---|
| `/etc/deproi/<name>.json` | root `0600` | This configuration. |
| `/etc/deproi/<name>.secrets.env` | root `0600` | Secrets for Compose interpolation (`compose.secrets_file`). |
| `/etc/deproi/<name>.betterstack.env` | root `0600` | `BETTERSTACK_UPTIME_TOKEN`, `BETTERSTACK_ERRORS_TOKEN`. |
| `/etc/deproi/<name>.cloudflare.env` | root `0600` | `CLOUDFLARE_API_TOKEN`. |
| `/etc/deproi/<name>.webhook.env` | root `0600` | `WEBHOOK_URL`. |
| `/var/lib/deproi/<name>/` | root `0700` | State: monitors to restore, the last post-deploy result. |
| `/run/lock/deproi-<name>.lock` | root `0600` | One deploy at a time. |
