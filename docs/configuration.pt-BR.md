[🇺🇸 English](configuration.md) · 🇧🇷 Português

# Referência da configuração

Cada ambiente tem um arquivo no servidor: **`/etc/deproi/<name>.json`**, lido por **`/usr/local/sbin/deproi-<name>`**. O nome do comando instalado escolhe o arquivo, e o `name` do arquivo precisa bater com ele. Nada no repositório, na conexão SSH ou nas variáveis de ambiente consegue apontar o Deproi para outro lugar.

- **Dono e modo:** `root:root`, sem escrita para o grupo nem para outros (`0600` recomendado). A pasta `/etc/deproi` também não pode ter escrita para outros. Caso contrário, o Deproi se recusa a rodar.
- **Rigor:** uma chave desconhecida é um erro que diz o nome da chave (`unknown key compose.profile`). Um erro de digitação nunca desliga uma proteção em silêncio.
- **Padrões seguros:** toda chave opcional tem um padrão. Um Deproi mais novo continua funcionando com um arquivo mais antigo.
- **Suporte no editor:** mantenha a linha `$schema` e o VS Code (e a maioria dos editores) vai autocompletar e validar contra o [`deproi.schema.json`](../deproi.schema.json). Ele só é lido pelo seu editor; se preferir, fixe-o na tag da sua versão.
- **Nada de segredos aqui.** Tokens e senhas ficam em arquivos separados, só do root (`0600`), para os quais este arquivo aponta.

## Um exemplo completo

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

## Nível superior

| Chave | Obrigatório | Padrão | O que faz |
|---|---|---|---|
| `name` | ✅ | — | Tem que ser igual ao `<name>` de `/usr/local/sbin/deproi-<name>`. Letras minúsculas, dígitos e `-`. |
| `language` | | `"en"` | Idioma das mensagens para pessoas: `"en"` ou `"pt-BR"`. A linha `result:` é sempre em inglês. |
| `checkout` | ✅ | — | O checkout git no servidor. [Detalhes](#checkout). |
| `compose` | ✅ | — | O projeto do Docker Compose. [Detalhes](#compose). |
| `url` | | nenhum | Endereço público, mostrado na mensagem de sucesso e usado como host padrão na purga do Cloudflare. |
| `script_path` | | `"deploy/deproi.py"` | Onde o projeto guarda a sua cópia do `deproi.py`. A autoatualização lê esse arquivo de cada commit. |
| `docs` | | O [guia de operação](operations.pt-BR.md) do Deproi | Link mostrado nas mensagens de falha: aponte para o seu próprio plano B. |
| `timeouts` | | veja abaixo | [Detalhes](#timeouts). |
| `build` | | veja abaixo | [Detalhes](#build). |
| `health_interval` | | `5` | Segundos entre duas verificações de saúde. |
| `min_free_disk_gb` | | `5` | Com menos espaço livre que isso em `/var/lib/docker`, o deploy para antes de mexer em qualquer coisa. |
| `hooks` | | nenhum | Comandos em pontos fixos do deploy. [Detalhes](#hooks). |
| `protected_services` | | nenhum | Serviços que não podem ser recriados enquanto estão ocupados. [Detalhes](#serviços-protegidos). |
| `integrations` | | nenhum | Better Stack, Cloudflare, webhook. [Detalhes](integrations.pt-BR.md). |
| `config_version` | | `1` | Versão do formato deste arquivo. |

## checkout

| Chave | Obrigatório | Padrão | O que faz |
|---|---|---|---|
| `path` | ✅ | — | Caminho absoluto do checkout, por exemplo `/srv/myapp-prod`. |
| `owner` | ✅ | — | O usuário dono do checkout. O git roda como esse usuário, nunca como root. Não pode ser `root`. |
| `branch` | ✅ | — | A branch que este ambiente publica. O checkout precisa estar nela. |
| `remote` | | `"origin"` | O remote git de onde buscar. |

O Deproi só avança o checkout (`git merge --ff-only`). Ele nunca roda `reset`, `clean`, `stash` nem `checkout`, então arquivos não rastreados (segredos, backups) ficam a salvo. Um checkout com alteração local em arquivos rastreados, ou com commits que o remote não tem, é recusado.

## compose

| Chave | Obrigatório | Padrão | O que faz |
|---|---|---|---|
| `project` | ✅ | — | Nome do projeto do Compose. Sempre passado com `--project-name`, então nenhum arquivo consegue desviar o deploy para outro projeto. |
| `web_service` | ✅ | — | O serviço cujo healthcheck decide entre sucesso e reversão. |
| `image` | ✅ | — | Repositório da imagem, **sem tag**. Todo serviço construído precisa usar `image: <image>:${DEPROI_TAG}`. |
| `files` | | `["compose.yaml"]` | Arquivos do Compose, relativos ao checkout. |
| `env_file` | | nenhum | Arquivo env versionado (valores não secretos). Quando definido, o `COMPOSE_PROJECT_NAME` dele precisa ser igual a `project`; o Deproi confere isso no commit buscado **antes** de mover o checkout. |
| `secrets_file` | | nenhum | Arquivo env não rastreado com segredos, passado depois do `env_file` para que os valores dele prevaleçam. Absoluto (recomendado: `/etc/deproi/<name>.secrets.env`, root `0600`) ou relativo ao checkout. |
| `profiles` | | nenhum | Perfis do Compose deste ambiente. |
| `service_suffix` | | nenhum | Quando definido, **todo** serviço da definição precisa terminar com ele (por exemplo `-prod`). Essa cerca impede que um serviço sem `profiles:` suba em todos os ambientes do mesmo servidor. |
| `tag_variables` | | `["DEPROI_TAG"]` | Variáveis que recebem a tag do commit (12 caracteres hexadecimais) quando o Compose interpola os arquivos. Adicione outras se o seu arquivo do Compose usar outros nomes (por exemplo, uma variável de release para telemetria). |

## timeouts

Tudo em segundos.

| Chave | Padrão | O que limita |
|---|---|---|
| `lock` | `1800` | A espera para outro deploy do mesmo ambiente terminar. |
| `build` | `2400` | `docker compose build`. |
| `migrations` | `2400` | Todos os ganchos `migrate` juntos. |
| `health` | `240` | A espera para o serviço web ficar saudável (e de novo depois de uma reversão). A espera também termina antes quando o Docker informa `unhealthy` três vezes seguidas. Apps que sobem rápido podem diminuí-lo. |
| `hook` | `600` | Cada gancho `pre_migrate` / `post_migrate` sem `timeout` próprio. |
| `post_deploy` | `300` | Cada gancho `post_deploy` sem `timeout` próprio. |

## build

| Chave | Padrão | O que faz |
|---|---|---|
| `low_priority` | `true` | Constrói com `nice -n 10 ionice -c3`, para o app continuar atendendo enquanto a imagem é construída. |
| `pull` | `false` | Adiciona `--pull` (sempre busca imagens base mais novas). |

## hooks

Um gancho é um comando que roda **na imagem nova**, via `docker compose run --rm --no-deps <service> <command…>`, antes de os serviços serem recriados. O comando é uma lista de argumentos, nunca uma string de shell.

Os serviços de terceiros (um banco de dados, um cache: qualquer coisa que não rode a sua imagem) são iniciados primeiro, se ainda não estiverem rodando, e o Deproi espera que fiquem saudáveis. Assim, as migrations funcionam também no primeiríssimo deploy. Dê ao seu banco de dados um `healthcheck:` (para o Postgres, `pg_isready`) para que "iniciado" signifique "pronto".

| Ponto | Quando | Padrão em caso de falha |
|---|---|---|
| `pre_migrate` | Depois do build, antes de qualquer mudança. Para verificações: checagens de deploy do framework, uma guarda que recusa migrations arriscadas. | `fail` |
| `migrate` | Migrations do banco de dados. Todos os ganchos `migrate` dividem o `timeouts.migrations`. | `fail` |
| `post_migrate` | Depois das migrations, antes de recriar: aquecer o cache, sincronizar feature flags… | `warn` |
| `post_deploy` | Em segundo plano, depois que a versão nova está no ar. Nunca muda o desfecho; o próximo deploy mostra o resultado dele. | `warn` (única opção) |

Cada gancho:

| Chave | Obrigatório | O que faz |
|---|---|---|
| `name` | ✅ | Identificador curto mostrado no log: letras minúsculas, dígitos, `-`, `_`. Único por ponto. |
| `command` | ✅ | O comando, como lista: `["python", "manage.py", "migrate"]`. |
| `service` | | A imagem de qual serviço roda o comando. Padrão: `compose.web_service`. |
| `env` | | Variáveis de ambiente extras: `{"COLLECTSTATIC": "0"}`. |
| `timeout` | | Segundos, substituindo o padrão para este gancho. |
| `on_failure` | | `fail` → `FAILED_NO_CHANGE` (exit 3) · `refuse` → `REFUSED` (exit 2) · `warn` → registra no log e segue. |

> A reversão não desfaz migrations. Escreva-as de forma que a versão anterior continue funcionando com o schema novo (primeiro expanda, contraia num deploy posterior).

## serviços protegidos

Para serviços que não podem ser parados no meio do trabalho, como um worker de fila rodando uma tarefa longa.

| Chave | Obrigatório | O que faz |
|---|---|---|
| `service` | ✅ | O serviço do Compose. Não pode ser o serviço web. |
| `busy_check` | ✅ | Roda com `docker exec` no contêiner dele. Saída `0` = livre, `1` = ocupado, qualquer outra = sem resposta (tratado como ocupado). |
| `quiesce` | | Opcional: pede que ele pare de pegar trabalho novo. O `busy_check` roda de novo logo em seguida, para nada escapar no meio. |
| `resume` | | Opcional: desfaz o `quiesce` quando o serviço acaba não sendo recriado. |

`busy_check`, `quiesce` e `resume` são listas de argumentos rodadas com `docker exec`, sem shell: use programas que existam na imagem (`["test", "!", "-e", "/tmp/working"]`, `["touch", "/tmp/paused"]`, `["node", "busy.js"]`).

O que acontece com cada serviço protegido:

| Estado | O que o Deproi faz | Na linha `result:` |
|---|---|---|
| Ainda sem contêiner | Cria junto com o resto | `updated` |
| Contêiner existe, mas está parado | Não mexe nele (alguém o parou de propósito) | `stopped` |
| Ocupado, ou sem resposta | Mantém na versão anterior; o deploy é `SUCCESS_PROTECTED_DEFERRED` | `deferred` |
| Livre | Recria depois dos outros serviços | `updated` |

Bom saber:

- **Ordem:** os outros serviços são recriados primeiro e depois os protegidos livres. Use o `quiesce` (e confira de novo) para que nenhuma tarefa comece no meio.
- **Reversão:** um serviço protegido livre que foi atualizado volta junto com o resto (`rolled_back`); um ocupado fica na versão nova.
- **Parada elegante:** trate o `SIGTERM` terminando a tarefa atual e defina `stop_grace_period` no Compose com a duração da tarefa mais longa. Isso também cobre a rara corrida entre a verificação de ocupado e a recriação.
- **Política de reinício:** dê a ele `restart: unless-stopped`. Um serviço protegido cujo contêiner existe mas está parado nunca é iniciado pelo Deproi (alguém pode tê-lo parado de propósito), então um que caiu sem política de reinício ficaria fora do ar.
- **Sempre ocupado:** um worker que nunca fica livre nunca é atualizado. Esvazie a fila ou rode o deploy de novo pelo Actions quando ele estiver livre.

## Arquivos ao lado da configuração

| Arquivo | Modo | Guarda |
|---|---|---|
| `/etc/deproi/<name>.json` | root `0600` | Esta configuração. |
| `/etc/deproi/<name>.secrets.env` | root `0600` | Segredos para a interpolação do Compose (`compose.secrets_file`). |
| `/etc/deproi/<name>.betterstack.env` | root `0600` | `BETTERSTACK_UPTIME_TOKEN`, `BETTERSTACK_ERRORS_TOKEN`. |
| `/etc/deproi/<name>.cloudflare.env` | root `0600` | `CLOUDFLARE_API_TOKEN`. |
| `/etc/deproi/<name>.webhook.env` | root `0600` | `WEBHOOK_URL`. |
| `/var/lib/deproi/<name>/` | root `0700` | Estado: monitores a restaurar, o último resultado do pós-deploy. |
| `/run/lock/deproi-<name>.lock` | root `0600` | Um deploy por vez. |
