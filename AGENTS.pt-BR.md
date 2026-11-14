[🇺🇸 English](AGENTS.md) · 🇧🇷 Português

> Esta é a tradução para humanos revisarem. Agentes: leiam o [AGENTS.md](AGENTS.md), em inglês.

# AGENTS.md — instruções para agentes de IA

Leia este arquivo inteiro antes de fazer qualquer coisa. Ele foi escrito para você, um agente de IA de programação. Siga-o ao pé da letra: cada regra existe porque quebrá-la abre uma brecha de segurança ou deixa um deploy que falha de um jeito confuso.

**Idioma:** responda ao humano no idioma dele. Mantenha código, chaves de configuração e comandos em inglês.

## Qual tarefa você está fazendo?

| Pediram para você… | Vá para |
|---|---|
| **Adicionar o Deproi a um projeto** (deploys automáticos do GitHub para um servidor) | [Implantar o Deproi num projeto](#implantar-o-deproi-num-projeto) |
| **Atualizar o Deproi** num projeto que já o usa | [Atualizar o Deproi num projeto](#atualizar-o-deproi-num-projeto) |
| **Explicar um deploy que falhou** | [Ler um deploy que falhou](#ler-um-deploy-que-falhou) |
| **Mudar o próprio Deproi** (este repositório) | [Trabalhar neste repositório](#trabalhar-neste-repositório) |

## Implantar o Deproi num projeto

### 1. As regras que você não pode quebrar

| # | Regra | Por quê |
|---|---|---|
| R1 | **Nunca coloque lógica de deploy no workflow do GitHub.** Use o template renderizado como está. Nada de passos extras que rodam comandos no servidor, nada de `ssh … "<command>"`. | O comando forçado do servidor é o que torna inofensiva uma chave vazada. Lógica no YAML passa o controle para quem pode editar o YAML. |
| R2 | **Nunca enfraqueça o lado do servidor:** mantenha `restrict,command="sudo -n /usr/local/sbin/deproi-<name>"` no `authorized_keys` e o `""` no fim da regra do sudo. Nunca adicione `deproi` ao grupo `docker`. | Cada um é uma camada do modelo de segurança. |
| R3 | **Nunca coloque segredos no repositório**, no workflow, no `deproi.json` ou nas suas mensagens. Segredos vão em arquivos só do root em `/etc/deproi/` (servidor) ou no GitHub environment (via `create-deploy-key.sh`). | O repositório pode ser público; os logs ficam guardados. |
| R4 | **Nunca edite o `deproi.py`.** Copie-o sem mudanças de uma release. Comportamento específico do projeto vai em ganchos e na configuração. | A autoatualização e o atualizador o comparam byte a byte com as releases; edições locais são sobrescritas e sinalizadas. |
| R5 | **Nunca rode comandos no servidor nem configure segredos do GitHub você mesmo**, a não ser que o humano lhe dê esse acesso explicitamente e peça. Prepare os comandos exatos; o humano os roda. | Root num servidor e segredos de produção são decisão do humano. |
| R6 | **Nunca chute valores de infraestrutura** (host, caminhos, usuários, mapeamento de branch para ambiente, domínio, comando de migration). Pergunte. | Um valor errado publica no lugar errado ou falha às 3 da manhã. |
| R7 | **Nunca use uma GitHub Action de terceiros** no workflow de deploy, e nunca substitua `StrictHostKeyChecking=yes`. | Proteção da cadeia de suprimentos e contra man-in-the-middle. |
| R8 | **Nunca faça commit direto numa branch de deploy** para "testar" a configuração. Use um pull request, como o projeto normalmente faz. | Push numa branch de deploy é um deploy de produção. |
| R9 | **Fixe o Deproi numa tag de release**, nunca na `main`. | Os scripts rodam como root; uma versão fixada e com checksum pode ser revisada. |

### 2. Quem faz o quê

| Tarefa | Você (agente) | Humano |
|---|---|---|
| Avaliar o projeto, propor mudanças | ✅ | revisa |
| Editar `compose.yaml`, Dockerfile, arquivo env, adicionar endpoint de saúde | ✅ | revisa |
| Copiar `deploy/deproi.py`, renderizar os workflows, escrever `docs/deploy.md` | ✅ | revisa |
| Rascunhar `/etc/deproi/<name>.json` (só o conteúdo) | ✅ | instala no servidor |
| Rodar `prepare-server.sh`, `doctor.sh`, o primeiro deploy manual | prepara os comandos exatos | 🖥️ roda |
| Rodar `create-deploy-key.sh` (chave, conferência da impressão digital, segredos do GitHub) | prepara o comando exato | 💻 roda |
| Fazer o merge do pull request, ativar revisores do environment | — | 🐙 faz |

### 3. Avalie o projeto

Faça estas verificações e anote as respostas. Não mude nada ainda.

1. **Compose:** existe um `compose.yaml` / `docker-compose.yml`? Quais serviços? Qual deles serve HTTP (o serviço web)? Se o arquivo não for `compose.yaml`, a configuração precisa de `compose.files`.
2. **Dockerfile:** o serviço web é construído a partir de um? A imagem tem `curl`/`wget` ou um runtime da linguagem para rodar uma sonda de saúde?
3. **Healthcheck:** existe um `HEALTHCHECK` ou `healthcheck:`? Existe um endpoint que falha quando a aplicação está quebrada? Se não, você vai adicionar um.
4. **Tags de imagem:** os serviços construídos definem `image:`? Você vai definir `image: <name>:${DEPROI_TAG:-local}`.
5. **Ambientes:** quais branches publicam onde (ex.: `main` → produção, `develop` → teste)? Vários ambientes dividem um servidor? Se sim, todo serviço precisa de um perfil e de um sufixo (`-prod`, `-test`).
6. **Migrations:** framework e comando (veja as [receitas](docs/recipes.pt-BR.md)). As migrations são retrocompatíveis (a versão anterior precisa continuar funcionando)? Aponte as arriscadas ao humano.
7. **Workers de longa duração:** workers de fila com jobs longos? Eles viram serviços protegidos com um `busy_check`.
   **Ensaie** se houver Docker disponível: commite na sua branch e rode
   `/tmp/deproi/scripts/try-locally.sh --project . --config myapp-prod.json --ref <sua branch>` (adicione `--secrets <arquivo>` com valores fictícios se o compose precisar). Tem que terminar com "Rehearsal passed". Coloque o resultado na descrição do pull request.
8. **Segredos:** quais variáveis são secretas? Elas vão para `/etc/deproi/<name>.secrets.env` e são referenciadas como `${VAR}` no compose.
9. **Deploy atual:** como o projeto faz deploy hoje? Algo que o Deproi precisa continuar fazendo (arquivos estáticos, purga de cache, notificações)? Mapeie cada item para um gancho ou integração. Se ele já roda no servidor, planeje a migração com o humano ([migrar de um deploy existente](docs/installation.pt-BR.md#migrar-de-um-deploy-existente)): um `COMPOSE_PROJECT_NAME` novo significa **volumes novos e vazios** — nunca deixe o primeiro deploy começar num banco de dados vazio por acidente.
10. **Servidor compartilhado:** cada ambiente precisa das suas próprias portas publicadas e do seu próprio `compose.image`, além do perfil e do sufixo.
11. **Valide localmente:** `docker compose --env-file deploy/<env>.compose.env --profile <env> config` precisa funcionar depois das suas mudanças.

Se o projeto nem roda em Docker Compose, pare e avise o humano: conteinerizá-lo é uma tarefa separada, a ser feita e revisada antes.

### 4. Pergunte ao humano — uma vez, tudo junto

Mande uma única mensagem com todas as perguntas que você não conseguiu responder pelo repositório. Use esta lista; tire o que você já sabe; nunca invente valores padrão para as cinco primeiras.

```text
Para configurar deploys automáticos com o Deproi eu preciso de:

1. Servidor: endereço (IP ou host) e porta SSH; versão do sistema (Ubuntu 22.04+/Debian 12+?).
2. No servidor: o caminho do checkout do projeto (ex.: /srv/myapp-prod) e o usuário Linux dono dele.
3. Ambientes: qual branch publica em qual ambiente (ex.: main → produção, develop → teste)?
   Eles dividem o mesmo servidor?
4. GitHub: o repositório (owner/name) e os nomes dos GitHub environments a usar (ex.: production, test).
5. URL pública de cada ambiente (aparece nas mensagens; usada na purga do Cloudflare).
6. Migrations: `<command>` é o comando de migration certo? Alguma migration que nunca pode rodar automaticamente?
7. Workers de longa duração que não podem ser reiniciados no meio de um job: <list> — como sabemos se um está ocupado?
8. Opcional: monitores do Better Stack, purga de cache do Cloudflare, um webhook do Slack/Discord?
9. Idioma das mensagens do Deproi neste servidor: inglês ou português do Brasil?
```

### 5. Mude o repositório

Trabalhe numa branch, nunca numa branch de deploy. Como referência de uma configuração pronta e correta, leia o [deproi-demo](https://github.com/rodrigo-pasini/deproi-demo): workflows renderizados e sem edição, `deploy/deproi.py` sem alteração, a configuração do servidor em `docs/deploy/`.

1. **Baixe uma release fixada do Deproi** numa pasta temporária e verifique-a:

   ```bash
   DEPROI_VERSION=0.2.0
   git clone --quiet --depth 1 --branch "v$DEPROI_VERSION" https://github.com/rodrigo-pasini/deproi /tmp/deproi
   curl -fsSL "https://github.com/rodrigo-pasini/deproi/releases/download/v$DEPROI_VERSION/SHA256SUMS" -o /tmp/deproi/SHA256SUMS
   (cd /tmp/deproi && sha256sum --check --ignore-missing SHA256SUMS && cd scripts && sha256sum --check --ignore-missing ../SHA256SUMS)
   ```

   Use a release mais recente listada em <https://github.com/rodrigo-pasini/deproi/releases>, não necessariamente o número acima.

2. **Copie o script, sem mudanças:** `mkdir -p deploy && cp /tmp/deproi/deproi.py deploy/deproi.py`.
3. **Aplique o [contrato do projeto](docs/project-contract.pt-BR.md):** healthcheck, `image: <image>:${DEPROI_TAG:-local}`, perfis e sufixo se o servidor for compartilhado, `deploy/<env>.compose.env` com `COMPOSE_PROJECT_NAME=<name>`, segredos como `${VAR}`.
4. **Renderize um workflow de deploy por ambiente:**

   ```bash
   /tmp/deproi/scripts/render-workflow.sh deploy --name myapp-prod --branch main --environment production \
       > .github/workflows/deploy-production.yml
   /tmp/deproi/scripts/render-workflow.sh update > .github/workflows/deproi-update.yml   # recomendado
   ```

   O `--name` é `<app>-<env>`, em minúsculas, e precisa ser idêntico no servidor. Não edite os arquivos renderizados. Cada workflow de deploy precisa acabar na branch que ele implanta (um push só roda os workflows da branch enviada).
5. **Rascunhe a configuração do servidor** de cada ambiente a partir de `/tmp/deproi/templates/server/deproi.example.json` e da [referência da configuração](docs/configuration.pt-BR.md). Mantenha-a fora do caminho de deploy do repositório: coloque-a na sua mensagem de entrega (ou em `docs/deploy/<name>.json.example` sem segredos, se o humano preferir versioná-la). Valide-a:

   ```bash
   python3 -c "import json,sys; sys.path.insert(0,'deploy'); import deproi; \
   deproi.parse_config(json.load(open('myapp-prod.json')), 'myapp-prod', home_of=lambda u: '/home/'+u); print('valid')"
   ```

6. **Escreva o `docs/deploy.md`** no projeto: ambientes, branches, caminhos no servidor, como ler um deploy que falhou, plano B (adapte o de [operação](docs/operations.pt-BR.md#plano-b-deploy-à-mão)) e um link para o Deproi. Defina `docs` na configuração com a URL desse arquivo.
7. **Confira:** `docker compose … config` funciona; o healthcheck falha quando a aplicação está quebrada (teste localmente se puder); nenhum segredo no diff.
8. **Abra um pull request** com as mudanças. Não faça o merge você mesmo.

### 6. Entregue ao humano

Mande isto, preenchido, depois que o pull request estiver aberto. Substitua cada `<…>`. Um bloco por ambiente. A ordem importa: o servidor é preparado a partir da branch de deploy, então o merge do pull request vem primeiro, com os deploys pausados.

````markdown
## Configuração do Deproi para <name> — o que você precisa rodar

O pull request <link> prepara o projeto (script do Deproi, workflow, mudanças no compose). Siga os passos nesta ordem.

### 1. 🐙 Pause os deploys e depois faça o merge
```bash
gh api -X PUT repos/<owner/repo>/environments/<github env> --silent
gh variable set DEPROI_PAUSED --repo <owner/repo> --env <github env> --body true
```
Depois faça o merge do pull request na <branch>. O workflow só escreve "paused".

### 2. 🖥️ No servidor (<host>), como um usuário com sudo
```bash
sudo install -d -o <owner> -g <owner> <checkout path>
sudo -u <owner> git clone -b <branch> <git URL> <checkout path>
V=<version>; B=https://github.com/rodrigo-pasini/deproi/releases/download/v$V
curl -fsSLO "$B/prepare-server.sh" -fsSLO "$B/doctor.sh" -fsSLO "$B/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS && chmod +x prepare-server.sh doctor.sh
sudo ./prepare-server.sh --name <name> --checkout <checkout path>
sudo nano /etc/deproi/<name>.json            # cole a configuração abaixo
sudo install -m 0600 /dev/null /etc/deproi/<name>.secrets.env && sudo nano /etc/deproi/<name>.secrets.env
sudo ./doctor.sh --name <name>               # precisa terminar com "All checks passed"
sudo /usr/local/sbin/deproi-<name>           # primeiro deploy à mão: precisa terminar com result: SUCCESS
```

<the JSON config>

Segredos a colocar no arquivo de segredos: <VAR1>, <VAR2> (valores do seu gerenciador de senhas).
<Se o projeto já roda neste servidor: o plano para dados/portas/credenciais, passo a passo, ANTES do primeiro deploy.>

### 3. 💻 Na sua máquina
```bash
V=<version>; B=https://github.com/rodrigo-pasini/deproi/releases/download/v$V
curl -fsSLO "$B/create-deploy-key.sh" -fsSLO "$B/SHA256SUMS"
sha256sum --check --ignore-missing SHA256SUMS && chmod +x create-deploy-key.sh
./create-deploy-key.sh --name <name> --host <host> --port <ssh port> --repo <owner/repo> --environment <github env> --branch <branch>
```
Ele mostra um comando `prepare-server.sh … --public-key …`: rode-o no servidor, na pasta do passo 2, com `--checkout <checkout path>`. Ele também pede que você compare a impressão digital do servidor.

### 4. 🐙 Retome e acompanhe
```bash
gh variable delete DEPROI_PAUSED --repo <owner/repo> --env <github env>
gh workflow run <workflow file> --repo <owner/repo> --ref <branch>
```
1. Actions → "Deploy <github env>": o resumo precisa mostrar `result: SUCCESS`.
2. Recomendado para produção: Settings → Environments → <github env> → Required reviewers.
3. Settings → Actions → General → permita que o GitHub Actions crie pull requests (para o deproi-update.yml).
4. Remova as credenciais do deploy antigo, se houver: <list>.

Mande para mim a saída do doctor.sh e a linha de resultado se algo não for SUCCESS.
````

### 7. Verifique

Peça evidências em vez de supor que funcionou:

- Saída do `doctor.sh` terminando com "All checks passed".
- A linha `result:` do deploy manual: `SUCCESS`.
- O resumo da primeira execução no Actions: `SUCCESS`, e `commit=` igual ao commit de merge (os 12 primeiros caracteres).

### 8. Erros comuns

| Erro | O que acontece | Faça assim |
|---|---|---|
| Sem healthcheck, ou um que sempre passa | Recusado (`no health check`), ou versões quebradas continuam no ar | Um endpoint de verdade, que falha quando a aplicação está quebrada |
| Serviço construído sem `image: <image>:${DEPROI_TAG}` | Recusado (`uses image …, but Deproi expects …`); reversão impossível | Ponha tag em todo serviço construído |
| Um serviço sem `profiles:` num servidor compartilhado | Recusado (`without the suffix`) — ele subiria em todos os ambientes | Perfil + sufixo em todo serviço |
| `--name` diferente entre servidor e workflow | O comando forçado da chave não existe: o job não consegue se conectar ou o `sudo` recusa | O mesmo `<app>-<env>` em todo lugar |
| `checkout.owner` é root, ou o checkout pertence ao root | Recusado pela validação da configuração | Um usuário comum é dono do checkout |
| Segredos no `compose.yaml` ou no arquivo env | Vazados no repositório | `${VAR}` + `/etc/deproi/<name>.secrets.env` |
| Migration destrutiva (drop column) no mesmo deploy da mudança de código | A reversão traz de volta código que precisa da coluna apagada | Expanda agora, contraia num deploy posterior |
| Editar o workflow renderizado "para adicionar um passo" | Quebra a R1 | Ganchos no servidor, integrações na configuração |
| Testar com push na branch de deploy | Um deploy de produção sem revisão | Pull request, depois merge |
| Esquecer o primeiro deploy manual | A primeira execução automática depura o servidor pelos logs do GitHub | `sudo /usr/local/sbin/deproi-<name>` antes |
| Passos no servidor "antes do merge" | O `prepare-server.sh` não encontra o `deploy/deproi.py` na branch de deploy | Pause (`DEPROI_PAUSED`), faça o merge e depois prepare o servidor |
| `COMPOSE_PROJECT_NAME` novo para um projeto que já roda ali | Volumes novos e vazios: a aplicação sobe com um banco de dados vazio | Copie os volumes antes (guia de instalação, "migrar de um deploy existente") |
| Porta SSH diferente de 22 não informada | O workflow não consegue se conectar | `create-deploy-key.sh --port <port>` (define `DEPROI_SSH_PORT`) |
| Mesmas portas ou mesmo nome de imagem para dois ambientes num servidor | Conflito de portas; a limpeza de um ambiente remove a imagem anterior do outro | `WEB_PORT` e `compose.image` por ambiente |
| Banco de dados sem `healthcheck:` | As migrations podem começar antes de ele aceitar conexões | Healthcheck com `pg_isready` / `mysqladmin ping` |

## Atualizar o Deproi num projeto

1. Se o projeto tem o `deproi-update.yml`, revise o pull request que ele abriu em vez de fazer à mão.
2. Senão: leia as notas de release entre o `DEPROI_VERSION` atual (em `deploy/deproi.py`) e o novo, principalmente chaves de configuração novas.
3. Substitua o `deploy/deproi.py` pelo arquivo da release nova, verificado contra o `SHA256SUMS` dela. Não mude mais nada nele.
4. Abra um pull request. Depois do merge, o próximo deploy de cada ambiente instala o script novo sozinho; a linha de resultado mostra `script=updated:<old>:<new>`.
5. Se as notas de release exigirem uma mudança de configuração, dê ao humano a mudança exata no JSON de `/etc/deproi/<name>.json` **antes** do merge.

## Ler um deploy que falhou

Peça as linhas `message:` e `result:` (resumo do Actions, ou `journalctl -t deproi-<name>` no servidor) e então:

| Resultado | Significado | Seu próximo passo |
|---|---|---|
| `REFUSED` | Uma pré-condição falhou; nada mudou. | A mensagem diz qual. Dê ao humano a correção (veja [operação](docs/operations.pt-BR.md)). |
| `FAILED_NO_CHANGE` | fetch, build ou um gancho falhou antes de recriar. | Leia o log do grupo que falhou; corrija num pull request. Lembre que migrations anteriores continuam aplicadas. |
| `FAILED_ROLLED_BACK` | A versão nova não ficou saudável; a anterior voltou. | Peça o `docker compose -p <project> logs` do serviço web da tentativa que falhou ou reproduza localmente; corrija num pull request. |
| `FAILED_ROLLBACK` | O ambiente está fora do ar. | Urgente: dê ao humano os comandos do [plano B](docs/operations.pt-BR.md#plano-b-deploy-à-mão) com uma tag que sabidamente funciona, depois investigue. |
| o resumo diz "did not answer" | O SSH falhou; nada mudou. | Confira `DEPROI_HOST`, `DEPROI_KNOWN_HOSTS`, `DEPROI_SSH_KEY` e a linha da chave no servidor (`doctor.sh`). |

## Trabalhar neste repositório

1. Siga todas as regras do [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md#regras-básicas). Elas são o modelo de segurança, não preferências de estilo.
2. Toda mudança de documentação é feita **nos dois** idiomas na mesma mudança: primeiro o arquivo em inglês, depois o par `*.pt-BR.md` com a mesma estrutura. Rode `python tools/check_docs_parity.py`.
3. O `deproi.py` continua um **arquivo único**, só com a biblioteca padrão, válido em Python 3.10. A autoatualização instala exatamente um arquivo.
4. As imagens em `docs/img/` são geradas: edite `tools/build_images.py` e rode-o; nunca edite os SVGs à mão.
5. Antes de terminar, rode `ruff check .`, `ruff format --check .`, `pytest`, a checagem de paridade e, quando a mudança tocar o caminho de deploy, `tests/e2e/run.sh`. Reporte os resultados reais.
6. Nunca adicione linhas de coautoria ou de atribuição a IA nos commits.
