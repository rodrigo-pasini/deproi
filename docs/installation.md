🇺🇸 English · [🇧🇷 Português](installation.pt-BR.md)

# Installation, step by step

About 20 minutes per environment. You work in three places, marked on every step:

| Mark | Where |
|---|---|
| 🖥️ **server** | An SSH session on the server, with `sudo`. |
| 💻 **machine** | Your computer, with `ssh-keygen` and the GitHub CLI (`gh auth login` done). |
| 🐙 **GitHub** | The project repository on github.com. |

In the examples the environment is called `myapp-prod`, it deploys the branch `main`, its GitHub environment is `production`, and Deproi is version `0.2.0` (use the [latest release](https://github.com/rodrigo-pasini/deproi/releases)). Use your own names: `<app>-<env>` is a good pattern. [deproi-demo](https://github.com/rodrigo-pasini/deproi-demo) is a repository set up exactly this way, if you want to see the end result first.

## Before you start

- **Server:** Linux with `git`, `sudo` and `/usr/bin/python3` 3.10 or newer (Ubuntu 22.04+, Debian 12+). Docker Engine with the Compose plugin — preferably [Docker's own packages](https://docs.docker.com/engine/install/), which include `buildx`; the distribution's packages work but warn about it.
- **Project:** follows the [project contract](project-contract.md), with `deploy/deproi.py` committed, on a branch with a pull request ready to merge.
- **Fetch access:** the user that will own the checkout must be able to `git fetch` the repository. For a private repository, give that user a read-only deploy key:

  ```bash
  sudo -u ubuntu ssh-keygen -t ed25519 -N "" -C "myapp-prod checkout" -f /home/ubuntu/.ssh/myapp_checkout
  sudo -u ubuntu cat /home/ubuntu/.ssh/myapp_checkout.pub
  # GitHub → repository → Settings → Deploy keys → Add (read-only), then:
  printf 'Host github.com\n  IdentityFile ~/.ssh/myapp_checkout\n' | sudo -u ubuntu tee -a /home/ubuntu/.ssh/config
  sudo -u ubuntu ssh -T git@github.com    # "successfully authenticated"
  ```

- **Already deploying this project on the server?** Read [moving from an existing deployment](#moving-from-an-existing-deployment) first.

## Rehearse first (optional, recommended)

💻 Before touching the server, rehearse the whole deploy on your machine. From a clone of Deproi, with Docker:

```bash
scripts/try-locally.sh --project ../myapp --config myapp-prod.json --ref my-branch \
    --secrets myapp-prod.secrets.env
```

A container plays the server: it runs `prepare-server.sh` and `doctor.sh`, installs your config, deploys over SSH with a locked key exactly like GitHub does, then deploys a second commit. If it ends with "Rehearsal passed", your project and config are ready; if not, the deploy log shows why.

## 1. 🐙 Pause deploys, then merge the project changes

The server is prepared from the deploy branch, so the changes (including `deploy/deproi.py` and the workflow) must be merged first. Pause the environment so the merge does not try to deploy yet:

```bash
gh api -X PUT repos/acme/myapp/environments/production --silent
gh variable set DEPROI_PAUSED --repo acme/myapp --env production --body true
```

Merge the pull request into `main`. The workflow runs, writes "paused" and connects to nothing.

## 2. 🖥️ Clone the project on the server

```bash
sudo install -d -o ubuntu -g ubuntu /srv/myapp-prod
sudo -u ubuntu git clone -b main git@github.com:acme/myapp.git /srv/myapp-prod
```

The checkout belongs to a normal user (here `ubuntu`), never root. Git will always run as that user.

## 3. 🖥️ Get Deproi's server scripts, verified

```bash
V=0.2.0
B=https://github.com/rodrigo-pasini/deproi/releases/download/v$V
curl -fsSLO "$B/prepare-server.sh" -fsSLO "$B/doctor.sh" -fsSLO "$B/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS     # both must say OK
chmod +x prepare-server.sh doctor.sh
less prepare-server.sh                            # read what you are about to run as root
```

## 4. 🖥️ Prepare the server

```bash
sudo ./prepare-server.sh --name myapp-prod --checkout /srv/myapp-prod
```

It checks the prerequisites, creates the `deproi` user, installs `/usr/local/sbin/deproi-myapp-prod`, writes the sudo rule (validated with `visudo`) and a starter `/etc/deproi/myapp-prod.json`. It is safe to run again.

## 5. 🖥️ Write the configuration and the secrets

```bash
sudo nano /etc/deproi/myapp-prod.json
```

Fill in the project, compose files, profiles, web service, image and hooks: see the [configuration reference](configuration.md). Then the secrets, if your compose file needs any:

```bash
sudo install -m 0600 /dev/null /etc/deproi/myapp-prod.secrets.env
sudo nano /etc/deproi/myapp-prod.secrets.env
```

## 6. 🖥️ First deploy, by hand

```bash
sudo ./doctor.sh --name myapp-prod
sudo /usr/local/sbin/deproi-myapp-prod
```

`doctor.sh` must end with "All checks passed" (a warning that there is no key yet is expected). The deploy must end with `result: SUCCESS`: it starts third-party services such as the database first, runs your hooks, then starts the app. Fix anything else now: it is much easier here than through GitHub.

## 7. 💻 Create the deploy key and store it in GitHub

```bash
V=0.2.0
curl -fsSLO "https://github.com/rodrigo-pasini/deproi/releases/download/v$V/create-deploy-key.sh"
curl -fsSLO "https://github.com/rodrigo-pasini/deproi/releases/download/v$V/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS && chmod +x create-deploy-key.sh
./create-deploy-key.sh --name myapp-prod --host 203.0.113.10 --port 22 \
    --repo acme/myapp --environment production --branch main
```

The script guides you through it:

1. It generates a new key and prints a `prepare-server.sh … --public-key "ssh-ed25519 …"` command. Run it **on the server** (🖥️), in the folder where you downloaded `prepare-server.sh`, replacing `<path of the checkout>` with `/srv/myapp-prod`.
2. It shows the server's host key fingerprint and asks you to compare it with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the server.
3. It configures the GitHub environment `production` (deploys only from `main`) and stores `DEPROI_SSH_KEY`, `DEPROI_KNOWN_HOSTS` and `DEPROI_HOST` in it. With `--port` other than 22, it also sets `DEPROI_SSH_PORT`.
4. It deletes the private key from your machine.

## 8. 🐙 Resume deploys and watch the first automatic one

```bash
gh variable delete DEPROI_PAUSED --repo acme/myapp --env production
gh workflow run deploy-production.yml --repo acme/myapp --ref main
```

Open **Actions → Deploy production**. The job summary shows the message and the `result:` line. From now on, every push to `main` deploys.

## 9. 🐙 Recommended for production

- **Settings → Environments → production → Required reviewers**: someone approves each deploy.
- **Settings → Rules**: protect `main` (pull requests, required checks). Push access to it is root on the server.
- **Settings → Actions → General**: allow GitHub Actions to create pull requests, if you use `deproi-update.yml`. GitHub does not run workflows on pull requests opened with the workflow's own token, so with required checks, close and reopen the updater's pull request to run them.
- To pause deploys again later: set `DEPROI_PAUSED` = `true` in the environment.

## Adding the workflow files

If an AI agent prepared the pull request, the workflows are already in it. Otherwise, from a clone of Deproi:

```bash
deproi/scripts/render-workflow.sh deploy --name myapp-prod --branch main --environment production \
    > myapp/.github/workflows/deploy-production.yml
deproi/scripts/render-workflow.sh update > myapp/.github/workflows/deproi-update.yml   # optional
```

A push only runs the workflow files that exist **on the pushed branch**: each environment's workflow must be merged into the branch it deploys (for example `deploy-staging.yml` into `develop`).

## Another environment

Repeat with another name, checkout, branch and GitHub environment (`myapp-test`, `/srv/myapp-test`, `develop`, `test`). Each environment has its own key, config, sudo rule and workflow. On a shared server, give each environment its own profile, service suffix, image name and published ports ([project contract](project-contract.md#3-a-profile-and-a-suffix-per-environment)).

## Moving from an existing deployment

If the project already runs on the server (a `deploy.sh`, a CI job that SSHes in, manual `docker compose up`):

1. **Data.** Compose prefixes volumes with the project name. With a new `COMPOSE_PROJECT_NAME` (for example `myapp-prod` instead of `myapp`), the new project starts with **new, empty volumes**. Back up, stop the old stack and copy the data before the first deploy:

   ```bash
   sudo docker volume ls                                  # e.g. myapp_pgdata
   cd /srv/myapp && sudo docker compose down              # no -v: keeps the volumes
   sudo docker volume create myapp-prod_pgdata
   sudo docker run --rm -v myapp_pgdata:/from:ro -v myapp-prod_pgdata:/to alpine cp -a /from/. /to/
   ```

2. **Ports.** The old stack holds the published ports: stop it right before the first deploy (a short outage), or publish different ports and switch the proxy.
3. **Same project name?** If the old stack already uses the project name Deproi will use, its containers whose services no longer exist are removed as orphans by the first deploy — stop long-running work first.
4. **Old credentials.** Remove what the old deploy used: secrets in GitHub (`gh secret delete …`), keys in `/root/.ssh/authorized_keys`, a `deploy.sh` in the repository.

## Undo

```bash
sudo ./prepare-server.sh --name myapp-prod --uninstall
```

It removes the sudo rule, the key line and the installed command. It keeps the config, secrets and state for you to delete by hand, and the running containers.
