🇺🇸 English · [🇧🇷 Português](operations.pt-BR.md)

# Operations

## Reading a deploy

In **Actions**, open the run. The **summary** shows the message and the result. The **log** has one collapsible group per step, each ending with its duration, and the failing step is marked with `::error::`.

The last lines are always:

```text
betterstack: off on this server
cloudflare: cache purged (app.example.com)
webhook: sent
post_deploy: post-deploy of abc123def456 in the background (previous deploy 111111111111: release registered)
message: myapp-prod published: commit abc123def456 is live at https://app.example.com (2 min).
result: SUCCESS commit=abc123def456 previous=111111111111 duration=94s protected=- step=cleanup script=up_to_date
```

| Field | Meaning |
|---|---|
| `commit` | The commit this deploy published (12 hex characters, also the image tag). |
| `previous` | The image the web service ran before (`-` on the first deploy). |
| `step` | The last step reached — on a failure, where it stopped. |
| `protected` | Each protected service: `updated`, `deferred`, `stopped` or `rolled_back`. |
| `script` | The self-update: `up_to_date`, `updated:<old>:<new>`, `pending`, `refused`, `not_checked`. |

## What to do for each result

| Result | Exit | What to do |
|---|---|---|
| `SUCCESS` | 0 | Nothing. |
| `SUCCESS_PROTECTED_DEFERRED` | 0 | Nothing: the busy service updates on the next deploy. |
| `REFUSED` | 2 | Read the message: it says what is off and how to fix it. Nothing was changed. |
| `FAILED_NO_CHANGE` | 3 | Open the failing step (fetch, build, hook). Fix and push. Migrations that ran stay applied. |
| `FAILED_ROLLED_BACK` | 4 | The new version was unhealthy; the previous one is back. Look at the new version's logs (below), fix, push. |
| `FAILED_ROLLBACK` | 5 | **The environment is down.** Go to [plan B](#plan-b-deploy-by-hand). |

When the summary says the server did not answer, nothing was changed: check `DEPROI_HOST`, `DEPROI_SSH_KEY` and `DEPROI_KNOWN_HOSTS` in the GitHub environment. When it says the connection dropped, the deploy finished on the server: read its result in syslog.

## Common refusals

| Message | Cause | Fix (on the server) |
|---|---|---|
| "local changes in …" | Someone edited tracked files in the checkout. | `sudo -u <owner> git -C <checkout> diff`, then commit them elsewhere or `git checkout -- <file>`. |
| "on branch X, not Y" | The checkout was switched. | `sudo -u <owner> git -C <checkout> switch <branch>` |
| "has commits that are not on origin" | Someone committed on the server. | Push those commits from the server, or move them away. |
| "untracked file in the way" | A new committed file already exists untracked on the server. | Move the untracked file away. |
| "points to project X" | The env file in the commit names another project. | Fix `COMPOSE_PROJECT_NAME` in the commit. |
| "without the suffix" | A service lacks `profiles:` or the suffix. | Fix `compose.yaml` in the commit. |
| "has no health check" | No `healthcheck:` and no `HEALTHCHECK`. | Add one ([project contract](project-contract.md)). |
| "Another deploy has been running…" | The previous deploy is still running (or stuck). | Wait, or check `ps aux | grep deproi` on the server. |

## Logs on the server

```bash
journalctl -t deproi-myapp-prod -n 50            # starts, results, post-deploy
journalctl -t deproi-myapp-prod | grep 'result:'  # history of results
sudo docker logs --tail 100 myapp-prod-web-prod-1
sudo docker ps -a --filter label=com.docker.compose.project=myapp-prod
```

`docker logs <container>` needs no env file. For `docker compose` commands, pass the same files Deproi uses (`--env-file deploy/prod.compose.env --env-file /etc/deproi/myapp-prod.secrets.env --profile prod`), or variables from the secrets file come out empty.

The new version's containers are gone after a rollback, but its build is kept: `docker image ls myapp`.

## Run a deploy again

**Actions → Deploy production → Run workflow** republishes the latest commit of the branch (useful after changing the server config or secrets). On the server: `sudo /usr/local/sbin/deproi-myapp-prod`.

Republishing the same commit force-recreates the project's own services (those running your image), so they pick up new secrets. Third-party services such as the database are left running, and busy protected services keep their usual rules.

## Pause deploys

Set the variable `DEPROI_PAUSED` = `true` in the GitHub environment. Pushes still run the workflow, which only writes "paused" and connects to nothing. Delete the variable to resume.

## Plan B: deploy by hand

When Deproi cannot recover (`FAILED_ROLLBACK`), publish a known-good version yourself:

```bash
cd /srv/myapp-prod
sudo docker image ls myapp                             # pick a tag that worked (12 hex characters)
sudo env DEPROI_TAG=<tag> docker compose -p myapp-prod --env-file deploy/prod.compose.env \
     --env-file /etc/deproi/myapp-prod.secrets.env --profile prod up -d web-prod
sudo docker ps --filter label=com.docker.compose.project=myapp-prod
```

Name the services to bring back (here `web-prod`), so a busy protected worker is not recreated in the middle of a job. Drop the secrets `--env-file` if the environment has none.

Then fix the branch. The next push deploys normally.

## Rotate the deploy key

Run `create-deploy-key.sh` again (💻) and `prepare-server.sh --public-key` with the new public key (🖥️). The old key line is replaced and the GitHub secret is overwritten.

## Upgrade Deproi

Replace `deploy/deproi.py` with the new release (or merge the pull request opened by `deproi-update.yml`) and push. The next deploy of each environment installs it by itself (`script=updated:…`). Read the release notes first: they list any new configuration key.

## Check an environment

```bash
sudo ./doctor.sh --name myapp-prod
```

Read-only: the installed command, the config, the checkout (branch, local changes, fetch access), secrets permissions, the sudo rule, the key line, Docker, free space and the last results.

## Better Stack monitors left with a grace period

If a deploy dies while monitors have their grace period, the next deploy restores them first. To restore by hand, the original values are in `/var/lib/deproi/<name>/monitors.json`.
