🇺🇸 English · [🇧🇷 Português](installation.pt-BR.md)

# Installation, step by step

About 20 minutes per environment. You work in three places, marked on every step:

| Mark | Where |
|---|---|
| 🖥️ **server** | An SSH session on the server, with `sudo`. |
| 💻 **machine** | Your computer, with `ssh-keygen` and the GitHub CLI (`gh auth login` done). |
| 🐙 **GitHub** | The project repository on github.com. |

In the examples the environment is called `myapp-prod`, it deploys the branch `main`, and its GitHub environment is `production`. Use your own names: `<app>-<env>` is a good pattern.

## Before you start

- A Linux server with Docker Engine and the Compose plugin (`docker compose version` works), `git`, `sudo`, and `/usr/bin/python3` 3.10 or newer (Ubuntu 22.04+, Debian 12+).
- The project already follows the [project contract](project-contract.md) and has `deploy/deproi.py` committed.
- The server can `git fetch` the repository (a read-only deploy key or a token for the checkout owner).

## 1. 🖥️ Clone the project on the server

```bash
sudo install -d -o ubuntu -g ubuntu /srv/myapp-prod
sudo -u ubuntu git clone git@github.com:acme/myapp.git /srv/myapp-prod
sudo -u ubuntu git -C /srv/myapp-prod switch main
```

The checkout belongs to a normal user (here `ubuntu`), never root. Git will always run as that user.

## 2. 🖥️ Get Deproi's server scripts

```bash
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v0.1.0/scripts/prepare-server.sh
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v0.1.0/scripts/doctor.sh
chmod +x prepare-server.sh doctor.sh
less prepare-server.sh   # read what you are about to run as root
```

## 3. 🖥️ Prepare the server

```bash
sudo ./prepare-server.sh --name myapp-prod --checkout /srv/myapp-prod
```

It checks the prerequisites, creates the `deproi` user, installs `/usr/local/sbin/deproi-myapp-prod`, writes the sudo rule (validated with `visudo`) and a starter `/etc/deproi/myapp-prod.json`. It is safe to run again.

## 4. 🖥️ Write the configuration

```bash
sudo nano /etc/deproi/myapp-prod.json
```

Fill in the project, profiles, web service, image and hooks: see the [configuration reference](configuration.md). Then the secrets, if your compose file needs any:

```bash
sudo install -m 0600 /dev/null /etc/deproi/myapp-prod.secrets.env
sudo nano /etc/deproi/myapp-prod.secrets.env
```

## 5. 🖥️ First deploy, by hand

```bash
sudo ./doctor.sh --name myapp-prod
sudo /usr/local/sbin/deproi-myapp-prod
```

`doctor.sh` must end with "All checks passed". The manual deploy must end with `result: SUCCESS`. Fix anything else now: it is much easier here than through GitHub.

## 6. 💻 Create the deploy key and store it in GitHub

```bash
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v0.1.0/scripts/create-deploy-key.sh
chmod +x create-deploy-key.sh
./create-deploy-key.sh --name myapp-prod --host 203.0.113.10 \
    --repo acme/myapp --environment production --branch main
```

The script guides you through it:

1. It generates a new key and shows a command to run **on the server** (🖥️), the same `prepare-server.sh` with `--public-key "ssh-ed25519 …"`.
2. It shows the server's host key fingerprint and asks you to compare it with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the server.
3. It creates the GitHub environment `production`, limited to `main`, and stores `DEPROI_SSH_KEY`, `DEPROI_KNOWN_HOSTS` and `DEPROI_HOST` in it.
4. It deletes the private key from your machine.

## 7. 💻 Add the workflow to the project

From a clone of Deproi (`git clone https://github.com/rodrigo-pasini/deproi`):

```bash
deproi/scripts/render-workflow.sh deploy --name myapp-prod --branch main --environment production \
    > myapp/.github/workflows/deploy-production.yml
# optional: pull requests when a new Deproi is released
deproi/scripts/render-workflow.sh update > myapp/.github/workflows/deproi-update.yml
```

Commit, open a pull request, merge it into `main`.

## 8. 🐙 Watch the first automatic deploy

Open **Actions → Deploy production**. The job summary shows the message and the `result:` line. From now on, every push to `main` deploys.

## 9. 🐙 Recommended for production

- **Settings → Environments → production → Required reviewers**: someone approves each deploy.
- **Settings → Rules**: protect `main` (pull requests, required checks). Push access to it is root on the server.
- To pause deploys without touching anything else: **Settings → Environments → production → Variables →** `DEPROI_PAUSED` = `true`.

## Another environment

Repeat with another name, checkout and branch (`myapp-test`, `/srv/myapp-test`, `develop`, environment `test`). Each environment has its own key, config, sudo rule and workflow. Environments on the same server never touch each other's services, thanks to the project name and the service suffix.

## Undo

```bash
sudo ./prepare-server.sh --name myapp-prod --uninstall
```

It removes the sudo rule, the key line and the installed command. It keeps the config, secrets and state for you to delete by hand, and the running containers.
