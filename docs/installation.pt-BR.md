[🇺🇸 English](installation.md) · 🇧🇷 Português

# Instalação, passo a passo

Cerca de 20 minutos por ambiente. Você trabalha em três lugares, marcados em cada passo:

| Marca | Onde |
|---|---|
| 🖥️ **servidor** | Uma sessão SSH no servidor, com `sudo`. |
| 💻 **máquina** | O seu computador, com `ssh-keygen` e o GitHub CLI (`gh auth login` já feito). |
| 🐙 **GitHub** | O repositório do projeto no github.com. |

Nos exemplos, o ambiente se chama `myapp-prod`, faz deploy da branch `main`, o GitHub environment dele é `production` e o Deproi está na versão `0.2.0` (use a [versão mais recente](https://github.com/rodrigo-pasini/deproi/releases)). Use os seus próprios nomes: `<app>-<env>` é um bom padrão. O [deproi-demo](https://github.com/rodrigo-pasini/deproi-demo) é um repositório configurado exatamente assim, se você quiser ver o resultado final antes.

## Antes de começar

- **Servidor:** Linux com `git`, `sudo` e `/usr/bin/python3` 3.10 ou mais novo (Ubuntu 22.04+, Debian 12+). Docker Engine com o plugin do Compose — de preferência os [pacotes do próprio Docker](https://docs.docker.com/engine/install/), que incluem o `buildx`; os pacotes da distribuição funcionam, mas mostram um aviso sobre isso.
- **Projeto:** segue o [contrato do projeto](project-contract.pt-BR.md), com o `deploy/deproi.py` commitado, numa branch com um pull request pronto para o merge.
- **Acesso de fetch:** o usuário que vai ser dono do checkout precisa conseguir dar `git fetch` no repositório. Para um repositório privado, dê a esse usuário uma deploy key só de leitura:

  ```bash
  sudo -u ubuntu ssh-keygen -t ed25519 -N "" -C "myapp-prod checkout" -f /home/ubuntu/.ssh/myapp_checkout
  sudo -u ubuntu cat /home/ubuntu/.ssh/myapp_checkout.pub
  # GitHub → repositório → Settings → Deploy keys → Add (só leitura), depois:
  printf 'Host github.com\n  IdentityFile ~/.ssh/myapp_checkout\n' | sudo -u ubuntu tee -a /home/ubuntu/.ssh/config
  sudo -u ubuntu ssh -T git@github.com    # "successfully authenticated"
  ```

- **Já faz deploy deste projeto no servidor?** Leia antes [migrar de um deploy existente](#migrar-de-um-deploy-existente).

## Ensaie antes (opcional, recomendado)

💻 Antes de mexer no servidor, ensaie o deploy inteiro na sua máquina. Num clone do Deproi, com Docker:

```bash
scripts/try-locally.sh --project ../myapp --config myapp-prod.json --ref my-branch \
    --secrets myapp-prod.secrets.env
```

Um contêiner faz o papel do servidor: ele roda o `prepare-server.sh` e o `doctor.sh`, instala a sua configuração, faz o deploy por SSH com a chave presa exatamente como o GitHub faz e depois implanta um segundo commit. Se terminar com "Rehearsal passed", o projeto e a configuração estão prontos; se não, o log do deploy mostra o motivo.

## 1. 🐙 Pause os deploys e faça o merge das mudanças do projeto

O servidor é preparado a partir da branch de deploy, então o merge das mudanças (incluindo o `deploy/deproi.py` e o workflow) precisa vir antes. Pause o ambiente para que o merge ainda não tente fazer deploy:

```bash
gh api -X PUT repos/acme/myapp/environments/production --silent
gh variable set DEPROI_PAUSED --repo acme/myapp --env production --body true
```

Faça o merge do pull request na `main`. O workflow roda, escreve "paused" e não se conecta a nada.

## 2. 🖥️ Clone o projeto no servidor

```bash
sudo install -d -o ubuntu -g ubuntu /srv/myapp-prod
sudo -u ubuntu git clone -b main git@github.com:acme/myapp.git /srv/myapp-prod
```

O checkout pertence a um usuário comum (aqui, `ubuntu`), nunca ao root. O git sempre vai rodar como esse usuário.

## 3. 🖥️ Baixe os scripts de servidor do Deproi, conferidos

```bash
V=0.2.0
B=https://github.com/rodrigo-pasini/deproi/releases/download/v$V
curl -fsSLO "$B/prepare-server.sh" -fsSLO "$B/doctor.sh" -fsSLO "$B/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS     # os dois precisam dizer OK
chmod +x prepare-server.sh doctor.sh
less prepare-server.sh                            # leia o que você vai rodar como root
```

## 4. 🖥️ Prepare o servidor

```bash
sudo ./prepare-server.sh --name myapp-prod --checkout /srv/myapp-prod
```

Ele confere os pré-requisitos, cria o usuário `deproi`, instala `/usr/local/sbin/deproi-myapp-prod`, escreve a regra do sudo (validada com `visudo`) e um `/etc/deproi/myapp-prod.json` inicial. Pode rodar de novo sem problema.

## 5. 🖥️ Escreva a configuração e os segredos

```bash
sudo nano /etc/deproi/myapp-prod.json
```

Preencha o projeto, os arquivos do Compose, os perfis, o serviço web, a imagem e os ganchos: veja a [referência da configuração](configuration.pt-BR.md). Depois, os segredos, se o seu arquivo do Compose precisar de algum:

```bash
sudo install -m 0600 /dev/null /etc/deproi/myapp-prod.secrets.env
sudo nano /etc/deproi/myapp-prod.secrets.env
```

## 6. 🖥️ Primeiro deploy, à mão

```bash
sudo ./doctor.sh --name myapp-prod
sudo /usr/local/sbin/deproi-myapp-prod
```

O `doctor.sh` precisa terminar com "All checks passed" (um aviso de que ainda não há chave é esperado). O deploy precisa terminar com `result: SUCCESS`: ele sobe primeiro os serviços de terceiros, como o banco de dados, roda os seus ganchos e depois sobe a aplicação. Corrija qualquer outra coisa agora: aqui é muito mais fácil do que pelo GitHub.

## 7. 💻 Crie a chave de deploy e guarde-a no GitHub

```bash
V=0.2.0
curl -fsSLO "https://github.com/rodrigo-pasini/deproi/releases/download/v$V/create-deploy-key.sh"
curl -fsSLO "https://github.com/rodrigo-pasini/deproi/releases/download/v$V/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS && chmod +x create-deploy-key.sh
./create-deploy-key.sh --name myapp-prod --host 203.0.113.10 --port 22 \
    --repo acme/myapp --environment production --branch main
```

O script guia você:

1. Ele gera uma chave nova e mostra um comando `prepare-server.sh … --public-key "ssh-ed25519 …"`. Rode-o **no servidor** (🖥️), na pasta onde você baixou o `prepare-server.sh`, trocando `<path of the checkout>` por `/srv/myapp-prod`.
2. Ele mostra a impressão digital da chave do host do servidor e pede que você a compare com `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` no servidor.
3. Ele configura o GitHub environment `production` (deploys só a partir da `main`) e guarda nele `DEPROI_SSH_KEY`, `DEPROI_KNOWN_HOSTS` e `DEPROI_HOST`. Com um `--port` diferente de 22, ele também define `DEPROI_SSH_PORT`.
4. Ele apaga a chave privada da sua máquina.

## 8. 🐙 Retome os deploys e acompanhe o primeiro automático

```bash
gh variable delete DEPROI_PAUSED --repo acme/myapp --env production
gh workflow run deploy-production.yml --repo acme/myapp --ref main
```

Abra **Actions → Deploy production**. O resumo do job mostra a mensagem e a linha `result:`. Daqui em diante, todo push na `main` faz deploy.

## 9. 🐙 Recomendado para produção

- **Settings → Environments → production → Required reviewers**: alguém aprova cada deploy.
- **Settings → Rules**: proteja a `main` (pull requests, checks obrigatórios). Acesso de push a ela equivale a root no servidor.
- **Settings → Actions → General**: permita que o GitHub Actions crie pull requests, se você usa o `deproi-update.yml`.
- Para pausar os deploys de novo mais tarde: defina `DEPROI_PAUSED` = `true` no environment.

## Adicionar os arquivos de workflow

Se um agente de IA preparou o pull request, os workflows já estão nele. Se não, a partir de um clone do Deproi:

```bash
deproi/scripts/render-workflow.sh deploy --name myapp-prod --branch main --environment production \
    > myapp/.github/workflows/deploy-production.yml
deproi/scripts/render-workflow.sh update > myapp/.github/workflows/deproi-update.yml   # opcional
```

Um push só roda os arquivos de workflow que existem **na branch enviada**: o workflow de cada ambiente precisa chegar, por merge, à branch que ele implanta (por exemplo, `deploy-staging.yml` na `develop`).

## Outro ambiente

Repita com outro nome, checkout, branch e GitHub environment (`myapp-test`, `/srv/myapp-test`, `develop`, `test`). Cada ambiente tem a sua própria chave, configuração, regra do sudo e workflow. Num servidor compartilhado, dê a cada ambiente o seu próprio perfil, sufixo de serviço, nome de imagem e portas publicadas ([contrato do projeto](project-contract.pt-BR.md#3-um-perfil-e-um-sufixo-por-ambiente)).

## Migrar de um deploy existente

Se o projeto já roda no servidor (um `deploy.sh`, um job de CI que entra por SSH, `docker compose up` à mão):

1. **Dados.** O Compose prefixa os volumes com o nome do projeto. Com um `COMPOSE_PROJECT_NAME` novo (por exemplo, `myapp-prod` em vez de `myapp`), o projeto novo começa com **volumes novos e vazios**. Faça backup, pare a stack antiga e copie os dados antes do primeiro deploy:

   ```bash
   sudo docker volume ls                                  # ex.: myapp_pgdata
   cd /srv/myapp && sudo docker compose down              # sem -v: mantém os volumes
   sudo docker volume create myapp-prod_pgdata
   sudo docker run --rm -v myapp_pgdata:/from:ro -v myapp-prod_pgdata:/to alpine cp -a /from/. /to/
   ```

2. **Portas.** A stack antiga ocupa as portas publicadas: pare-a logo antes do primeiro deploy (uma queda curta) ou publique portas diferentes e troque o proxy.
3. **Mesmo nome de projeto?** Se a stack antiga já usa o nome de projeto que o Deproi vai usar, os contêineres dela cujos serviços não existem mais são removidos como órfãos no primeiro deploy — pare antes qualquer trabalho demorado.
4. **Credenciais antigas.** Remova o que o deploy antigo usava: segredos no GitHub (`gh secret delete …`), chaves em `/root/.ssh/authorized_keys`, um `deploy.sh` no repositório.

## Desfazer

```bash
sudo ./prepare-server.sh --name myapp-prod --uninstall
```

Ele remove a regra do sudo, a linha da chave e o comando instalado. Mantém a configuração, os segredos e o estado para você apagar à mão, e também os contêineres em execução.
