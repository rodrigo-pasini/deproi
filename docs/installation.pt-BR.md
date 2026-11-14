[🇺🇸 English](installation.md) · 🇧🇷 Português

# Instalação, passo a passo

Cerca de 20 minutos por ambiente. Você trabalha em três lugares, marcados em cada passo:

| Marca | Onde |
|---|---|
| 🖥️ **servidor** | Uma sessão SSH no servidor, com `sudo`. |
| 💻 **máquina** | O seu computador, com `ssh-keygen` e o GitHub CLI (`gh auth login` já feito). |
| 🐙 **GitHub** | O repositório do projeto no github.com. |

Nos exemplos, o ambiente se chama `myapp-prod`, faz deploy da branch `main`, e o GitHub environment dele é `production`. Use os seus próprios nomes: `<app>-<env>` é um bom padrão.

## Antes de começar

- Um servidor Linux com Docker Engine e o plugin do Compose (`docker compose version` funciona), `git`, `sudo` e `/usr/bin/python3` 3.10 ou mais novo (Ubuntu 22.04+, Debian 12+).
- O projeto já segue o [contrato do projeto](project-contract.pt-BR.md) e tem o `deploy/deproi.py` commitado.
- O servidor consegue dar `git fetch` no repositório (uma deploy key só de leitura ou um token para o dono do checkout).

## 1. 🖥️ Clone o projeto no servidor

```bash
sudo install -d -o ubuntu -g ubuntu /srv/myapp-prod
sudo -u ubuntu git clone git@github.com:acme/myapp.git /srv/myapp-prod
sudo -u ubuntu git -C /srv/myapp-prod switch main
```

O checkout pertence a um usuário comum (aqui, `ubuntu`), nunca ao root. O git sempre vai rodar como esse usuário.

## 2. 🖥️ Baixe os scripts de servidor do Deproi

```bash
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v0.1.0/scripts/prepare-server.sh
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v0.1.0/scripts/doctor.sh
chmod +x prepare-server.sh doctor.sh
less prepare-server.sh   # leia o que você vai rodar como root
```

## 3. 🖥️ Prepare o servidor

```bash
sudo ./prepare-server.sh --name myapp-prod --checkout /srv/myapp-prod
```

Ele confere os pré-requisitos, cria o usuário `deproi`, instala `/usr/local/sbin/deproi-myapp-prod`, escreve a regra do sudo (validada com `visudo`) e um `/etc/deproi/myapp-prod.json` inicial. Pode rodar de novo sem problema.

## 4. 🖥️ Escreva a configuração

```bash
sudo nano /etc/deproi/myapp-prod.json
```

Preencha o projeto, os perfis, o serviço web, a imagem e os ganchos: veja a [referência da configuração](configuration.pt-BR.md). Depois, os segredos, se o seu arquivo do Compose precisar de algum:

```bash
sudo install -m 0600 /dev/null /etc/deproi/myapp-prod.secrets.env
sudo nano /etc/deproi/myapp-prod.secrets.env
```

## 5. 🖥️ Primeiro deploy, à mão

```bash
sudo ./doctor.sh --name myapp-prod
sudo /usr/local/sbin/deproi-myapp-prod
```

O `doctor.sh` precisa terminar com "All checks passed". O deploy manual precisa terminar com `result: SUCCESS`. Corrija qualquer outra coisa agora: aqui é muito mais fácil do que pelo GitHub.

## 6. 💻 Crie a chave de deploy e guarde-a no GitHub

```bash
curl -fsSLO https://raw.githubusercontent.com/rodrigo-pasini/deproi/v0.1.0/scripts/create-deploy-key.sh
chmod +x create-deploy-key.sh
./create-deploy-key.sh --name myapp-prod --host 203.0.113.10 \
    --repo acme/myapp --environment production --branch main
```

O script guia você:

1. Ele gera uma chave nova e mostra um comando para rodar **no servidor** (🖥️): o mesmo `prepare-server.sh` com `--public-key "ssh-ed25519 …"`.
2. Ele mostra a impressão digital da chave do host do servidor e pede que você a compare com `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` no servidor.
3. Ele cria o GitHub environment `production`, limitado à `main`, e guarda nele `DEPROI_SSH_KEY`, `DEPROI_KNOWN_HOSTS` e `DEPROI_HOST`.
4. Ele apaga a chave privada da sua máquina.

## 7. 💻 Adicione o workflow ao projeto

A partir de um clone do Deproi (`git clone https://github.com/rodrigo-pasini/deproi`):

```bash
deproi/scripts/render-workflow.sh deploy --name myapp-prod --branch main --environment production \
    > myapp/.github/workflows/deploy-production.yml
# opcional: pull requests quando sair um Deproi novo
deproi/scripts/render-workflow.sh update > myapp/.github/workflows/deproi-update.yml
```

Faça o commit, abra um pull request e faça o merge na `main`.

## 8. 🐙 Acompanhe o primeiro deploy automático

Abra **Actions → Deploy production**. O resumo do job mostra a mensagem e a linha `result:`. Daqui em diante, todo push na `main` faz deploy.

## 9. 🐙 Recomendado para produção

- **Settings → Environments → production → Required reviewers**: alguém aprova cada deploy.
- **Settings → Rules**: proteja a `main` (pull requests, checks obrigatórios). Acesso de push a ela equivale a root no servidor.
- Para pausar os deploys sem mexer em mais nada: **Settings → Environments → production → Variables →** `DEPROI_PAUSED` = `true`.

## Outro ambiente

Repita com outro nome, checkout e branch (`myapp-test`, `/srv/myapp-test`, `develop`, environment `test`). Cada ambiente tem a sua própria chave, configuração, regra do sudo e workflow. Ambientes no mesmo servidor nunca mexem nos serviços uns dos outros, graças ao nome do projeto e ao sufixo dos serviços.

## Desfazer

```bash
sudo ./prepare-server.sh --name myapp-prod --uninstall
```

Ele remove a regra do sudo, a linha da chave e o comando instalado. Mantém a configuração, os segredos e o estado para você apagar à mão, e também os contêineres em execução.
