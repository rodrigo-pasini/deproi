🇺🇸 English · [🇧🇷 Português](AGENTS.pt-BR.md)

# AGENTS.md — instructions for AI agents

Read this whole file before doing anything. It is written for you, an AI coding agent. Follow it literally: every rule exists because breaking it either opens a security hole or leaves a deploy that fails in a confusing way.

**Language:** answer the human in the human's language. Keep code, config keys and commands in English.

## Which task are you doing?

| You were asked to… | Go to |
|---|---|
| **Add Deproi to a project** (automatic deploys from GitHub to a server) | [Implementing Deproi in a project](#implementing-deproi-in-a-project) |
| **Upgrade Deproi** in a project that already uses it | [Upgrading Deproi in a project](#upgrading-deproi-in-a-project) |
| **Explain a failed deploy** | [Reading a failed deploy](#reading-a-failed-deploy) |
| **Change Deproi itself** (this repository) | [Working on this repository](#working-on-this-repository) |

## Implementing Deproi in a project

### 1. The rules you must not break

| # | Rule | Why |
|---|---|---|
| R1 | **Never put deploy logic in the GitHub workflow.** Use the rendered template as is. No extra steps that run commands on the server, no `ssh … "<command>"`. | The server's forced command is what makes a leaked key harmless. Logic in the YAML moves control to whoever can edit the YAML. |
| R2 | **Never weaken the server side:** keep `restrict,command="sudo -n /usr/local/sbin/deproi-<name>"` in `authorized_keys` and the trailing `""` in the sudo rule. Never add `deproi` to the `docker` group. | Each one is a layer of the security model. |
| R3 | **Never put secrets in the repository**, in the workflow, in `deproi.json` or in your messages. Secrets go in root-only files under `/etc/deproi/` (server) or in the GitHub environment (via `create-deploy-key.sh`). | The repository may be public; logs are kept. |
| R4 | **Never edit `deproi.py`.** Copy it unchanged from a release. Project-specific behaviour goes in hooks and config. | The self-update and the updater compare it byte by byte with releases; local edits are overwritten and flagged. |
| R5 | **Never run commands on the server or set GitHub secrets yourself** unless the human explicitly gives you that access and asks you to. Prepare exact commands; the human runs them. | Root on a server and production secrets are the human's call. |
| R6 | **Never guess infrastructure values** (host, paths, users, branch-to-environment mapping, domain, migration command). Ask. | A wrong value deploys to the wrong place or fails at 3 a.m. |
| R7 | **Never use a third-party GitHub Action** in the deploy workflow, and never replace `StrictHostKeyChecking=yes`. | Supply chain and man-in-the-middle protection. |
| R8 | **Never commit to a deploy branch directly** to "test" the setup. Use a pull request, as the project normally does. | Push to a deploy branch is a production deploy. |
| R9 | **Pin Deproi to a release tag**, never `main`. | The scripts run as root; a pinned, checksummed version is reviewable. |

### 2. Who does what

| Task | You (agent) | Human |
|---|---|---|
| Assess the project, propose changes | ✅ | reviews |
| Edit `compose.yaml`, Dockerfile, env file, add health endpoint | ✅ | reviews |
| Copy `deploy/deproi.py`, render workflows, write `docs/deploy.md` | ✅ | reviews |
| Draft `/etc/deproi/<name>.json` (content only) | ✅ | installs it on the server |
| Run `prepare-server.sh`, `doctor.sh`, the first manual deploy | prepares the exact commands | 🖥️ runs them |
| Run `create-deploy-key.sh` (key, fingerprint check, GitHub secrets) | prepares the exact command | 💻 runs it |
| Merge the pull request, enable environment reviewers | — | 🐙 does it |

### 3. Assess the project

Run these checks and write down the answers. Do not change anything yet.

1. **Compose:** is there a `compose.yaml` / `docker-compose.yml`? Which services? Which one serves HTTP (the web service)?
2. **Dockerfile:** does the web service build from one? Does the image have `curl`/`wget` or a language runtime to run a health probe?
3. **Health check:** is there a `HEALTHCHECK` or `healthcheck:`? Is there an endpoint that fails when the app is broken? If not, you will add one.
4. **Image tags:** do built services set `image:`? You will set `image: <name>:${DEPROI_TAG:-local}`.
5. **Environments:** which branches deploy where (e.g. `main` → production, `develop` → test)? Do several environments share one server? If yes, every service needs a profile and a suffix (`-prod`, `-test`).
6. **Migrations:** framework and command (see [recipes](docs/recipes.md)). Are migrations backwards compatible (the previous version must keep working)? Flag risky ones to the human.
7. **Long-running workers:** queue workers with long jobs? They become protected services with a `busy_check`.
8. **Secrets:** which variables are secret? They move to `/etc/deproi/<name>.secrets.env` and are referenced as `${VAR}` in compose.
9. **Current deploy:** how does the project deploy today? Anything Deproi must keep doing (static files, cache purge, notifications)? Map each to a hook or integration.
10. **Validate locally:** `docker compose --env-file deploy/<env>.compose.env --profile <env> config` must succeed after your changes.

If the project does not run in Docker Compose at all, stop and tell the human: containerising it is a separate task, to be done and reviewed first.

### 4. Ask the human — once, all together

Send one message with every question you could not answer from the repository. Use this list; drop what you already know; never invent defaults for the first five.

```text
To set up automatic deploys with Deproi I need:

1. Server: address (IP or host) and SSH port; OS version (Ubuntu 22.04+/Debian 12+?).
2. On the server: the path of the project checkout (e.g. /srv/myapp-prod) and the Linux user that owns it.
3. Environments: which branch deploys to which environment (e.g. main → production, develop → test)?
   Do they share the same server?
4. GitHub: the repository (owner/name) and the GitHub environment names to use (e.g. production, test).
5. Public URL of each environment (shown in messages; used for the Cloudflare purge).
6. Migrations: is `<command>` the right migration command? Any migration that must never run automatically?
7. Long-running workers that must not be restarted mid-job: <list> — how do we tell if one is busy?
8. Optional: Better Stack monitors, Cloudflare cache purge, a Slack/Discord webhook?
9. Language for Deproi's messages on this server: English or Brazilian Portuguese?
```

### 5. Change the repository

Work on a branch, never on a deploy branch.

1. **Get a pinned Deproi release** into a temporary folder and verify it:

   ```bash
   DEPROI_VERSION=0.1.0
   git clone --quiet --depth 1 --branch "v$DEPROI_VERSION" https://github.com/rodrigo-pasini/deproi /tmp/deproi
   curl -fsSL "https://github.com/rodrigo-pasini/deproi/releases/download/v$DEPROI_VERSION/SHA256SUMS" -o /tmp/deproi/SHA256SUMS
   (cd /tmp/deproi && sha256sum --check --ignore-missing SHA256SUMS)
   ```

   Use the latest release listed at <https://github.com/rodrigo-pasini/deproi/releases>, not necessarily the number above.

2. **Copy the script, unchanged:** `mkdir -p deploy && cp /tmp/deproi/deproi.py deploy/deproi.py`.
3. **Apply the [project contract](docs/project-contract.md):** health check, `image: <image>:${DEPROI_TAG:-local}`, profiles and suffix if the server is shared, `deploy/<env>.compose.env` with `COMPOSE_PROJECT_NAME=<name>`, secrets as `${VAR}`.
4. **Render one deploy workflow per environment:**

   ```bash
   /tmp/deproi/scripts/render-workflow.sh deploy --name myapp-prod --branch main --environment production \
       > .github/workflows/deploy-production.yml
   /tmp/deproi/scripts/render-workflow.sh update > .github/workflows/deproi-update.yml   # recommended
   ```

   `--name` is `<app>-<env>`, lowercase, and must be identical on the server. Do not edit the rendered files.
5. **Draft the server config** for each environment from `/tmp/deproi/templates/server/deproi.example.json` and the [configuration reference](docs/configuration.md). Keep it out of the repository's deploy path: put it in your handover message (or in `docs/deploy/<name>.json.example` without secrets, if the human prefers it versioned). Validate it:

   ```bash
   python3 -c "import json,sys; sys.path.insert(0,'deploy'); import deproi; \
   deproi.parse_config(json.load(open('myapp-prod.json')), 'myapp-prod', home_of=lambda u: '/home/'+u); print('valid')"
   ```

6. **Write `docs/deploy.md`** in the project: environments, branches, server paths, how to read a failed deploy, plan B (adapt [operations](docs/operations.md#plan-b-deploy-by-hand)), and a link to Deproi. Set `docs` in the config to this file's URL.
7. **Check:** `docker compose … config` works; the health check fails when the app is broken (try it locally if you can); no secret in the diff.
   **Rehearse it** if Docker is available: commit on your branch, then
   `/tmp/deproi/scripts/try-locally.sh --project . --config myapp-prod.json --ref <your branch>` (add `--secrets <file>` with dummy values if the compose file needs them). It must end with "Rehearsal passed". Include the result in the pull request description.
8. **Open a pull request** with the changes. Do not merge it yourself.

### 6. Hand over to the human

Send this, filled in, after the pull request is open. Replace every `<…>`. One block per environment.

````markdown
## Deproi setup for <name> — what you need to run

The pull request <link> adds the workflow and prepares the project. Before merging it:

### 🖥️ On the server (<host>), as a user with sudo
```bash
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v<version>/scripts/prepare-server.sh
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v<version>/scripts/doctor.sh
chmod +x prepare-server.sh doctor.sh
sudo ./prepare-server.sh --name <name> --checkout <checkout path>
sudo nano /etc/deproi/<name>.json            # paste the config below
sudo install -m 0600 /dev/null /etc/deproi/<name>.secrets.env && sudo nano /etc/deproi/<name>.secrets.env
sudo ./doctor.sh --name <name>               # must end with "All checks passed"
sudo /usr/local/sbin/deproi-<name>           # first deploy by hand: must end with result: SUCCESS
```

<the JSON config>

Secrets to put in the secrets file: <VAR1>, <VAR2> (values from your password manager).

### 💻 On your machine
```bash
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v<version>/scripts/create-deploy-key.sh
chmod +x create-deploy-key.sh
./create-deploy-key.sh --name <name> --host <host> --repo <owner/repo> --environment <github env> --branch <branch>
```
It will ask you to run one more command on the server and to compare the server's fingerprint.

### 🐙 On GitHub
1. Merge the pull request into <branch>. The first automatic deploy starts.
2. Actions → "Deploy <github env>": the summary must show `result: SUCCESS`.
3. Recommended for production: Settings → Environments → <github env> → Required reviewers.
4. Settings → Actions → General → allow GitHub Actions to create pull requests (for deproi-update.yml).

Send me the output of doctor.sh and the result line if anything is not SUCCESS.
````

### 7. Verify

Ask for evidence instead of assuming it worked:

- `doctor.sh` output ending with "All checks passed".
- The manual deploy's `result:` line: `SUCCESS`.
- The first Actions run's summary: `SUCCESS`, and `commit=` equal to the merge commit (first 12 characters).

### 8. Common mistakes

| Mistake | What happens | Do instead |
|---|---|---|
| No health check, or one that always passes | Refused (`no health check`), or broken versions stay live | A real endpoint that fails when the app is broken |
| Built service without `image: <image>:${DEPROI_TAG}` | Refused (`uses image …, but Deproi expects …`); no rollback possible | Tag every built service |
| A service without `profiles:` on a shared server | Refused (`without the suffix`) — it would start in every environment | Profile + suffix on every service |
| `--name` differs between server and workflow | The key's forced command does not exist: the job fails to connect or `sudo` refuses | Same `<app>-<env>` everywhere |
| `checkout.owner` is root, or the checkout belongs to root | Refused by the config validation | A normal user owns the checkout |
| Secrets in `compose.yaml` or the env file | Leaked in the repository | `${VAR}` + `/etc/deproi/<name>.secrets.env` |
| Destructive migration (drop column) in the same deploy as the code change | The rollback brings back code that needs the dropped column | Expand now, contract in a later deploy |
| Editing the rendered workflow "to add a step" | Breaks R1 | Hooks on the server, integrations in the config |
| Testing by pushing to the deploy branch | An unreviewed production deploy | Pull request, then merge |
| Forgetting the first manual deploy | The first automatic run debugs the server through GitHub logs | `sudo /usr/local/sbin/deproi-<name>` first |

## Upgrading Deproi in a project

1. If the project has `deproi-update.yml`, review the pull request it opened instead of doing it by hand.
2. Otherwise: read the release notes between the current `DEPROI_VERSION` (in `deploy/deproi.py`) and the new one, especially new configuration keys.
3. Replace `deploy/deproi.py` with the new release file, verified against its `SHA256SUMS`. Change nothing else in it.
4. Open a pull request. After the merge, each environment's next deploy installs the new script by itself; its result line shows `script=updated:<old>:<new>`.
5. If the release notes require a config change, give the human the exact JSON change for `/etc/deproi/<name>.json` **before** the merge.

## Reading a failed deploy

Ask for the `message:` and `result:` lines (Actions summary, or `journalctl -t deproi-<name>` on the server), then:

| Result | Meaning | Your next step |
|---|---|---|
| `REFUSED` | A precondition failed; nothing changed. | The message names it. Give the human the fix (see [operations](docs/operations.md)). |
| `FAILED_NO_CHANGE` | fetch, build or a hook failed before recreating. | Read the failing group's log; fix in a pull request. Note that earlier migrations stay applied. |
| `FAILED_ROLLED_BACK` | The new version was unhealthy; the previous one is back. | Ask for `docker compose -p <project> logs` of the web service from the failed attempt or reproduce locally; fix in a pull request. |
| `FAILED_ROLLBACK` | The environment is down. | Urgent: give the human the [plan B](docs/operations.md#plan-b-deploy-by-hand) commands with a known-good tag, then investigate. |
| summary says "did not answer" | SSH failed; nothing changed. | Check `DEPROI_HOST`, `DEPROI_KNOWN_HOSTS`, `DEPROI_SSH_KEY`, the key line on the server (`doctor.sh`). |

## Working on this repository

1. Follow every rule in [CONTRIBUTING.md](CONTRIBUTING.md#ground-rules). They are the security model, not style preferences.
2. Every documentation change is made in **both** languages in the same change: the English file first, then the `*.pt-BR.md` twin with the same structure. Run `python tools/check_docs_parity.py`.
3. `deproi.py` stays a **single file**, standard library only, valid Python 3.10. Its self-update installs exactly one file.
4. Images in `docs/img/` are generated: edit `tools/build_images.py` and run it; never edit the SVGs by hand.
5. Before finishing, run `ruff check .`, `ruff format --check .`, `pytest`, the parity check and, when the change touches the deploy path, `tests/e2e/run.sh`. Report the real results.
6. Never add co-author or AI attribution lines to commits.
