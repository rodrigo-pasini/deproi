[🇺🇸 English](operations.md) · 🇧🇷 Português

# Operação

## Lendo um deploy

Em **Actions**, abra a execução. O **resumo** mostra a mensagem e o resultado. O **log** tem um grupo recolhível por passo, cada um terminando com sua duração, e o passo que falhou vem marcado com `::error::`.

As últimas linhas são sempre:

```text
betterstack: desligado neste servidor
cloudflare: cache purgado (app.example.com)
webhook: enviado
post_deploy: pós-deploy de abc123def456 em segundo plano (deploy anterior 111111111111: release registrada)
message: myapp-prod publicado: commit abc123def456 no ar em https://app.example.com (2 min).
result: SUCCESS commit=abc123def456 previous=111111111111 duration=94s protected=- step=cleanup script=up_to_date
```

| Campo | Significado |
|---|---|
| `commit` | O commit que este deploy publicou (12 caracteres hexadecimais, também a tag da imagem). |
| `previous` | A imagem que o serviço web rodava antes (`-` no primeiro deploy). |
| `step` | O último passo alcançado — numa falha, onde parou. |
| `protected` | Cada serviço protegido: `updated`, `deferred`, `stopped` ou `rolled_back`. |
| `script` | A autoatualização: `up_to_date`, `updated:<old>:<new>`, `pending`, `refused`, `not_checked`. |

## O que fazer em cada resultado

| Resultado | Saída | O que fazer |
|---|---|---|
| `SUCCESS` | 0 | Nada. |
| `SUCCESS_PROTECTED_DEFERRED` | 0 | Nada: o serviço ocupado atualiza no próximo deploy. |
| `REFUSED` | 2 | Leia a mensagem: ela diz o que está errado e como corrigir. Nada foi alterado. |
| `FAILED_NO_CHANGE` | 3 | Abra o passo que falhou (fetch, build, gancho). Corrija e faça push. Migrations que rodaram continuam aplicadas. |
| `FAILED_ROLLED_BACK` | 4 | A versão nova não ficou saudável; a anterior voltou. Veja os logs da versão nova (abaixo), corrija e faça push. |
| `FAILED_ROLLBACK` | 5 | **O ambiente está fora do ar.** Vá para o [plano B](#plano-b-deploy-à-mão). |

Quando o resumo diz que o servidor não respondeu, nada foi alterado: confira `DEPROI_HOST`, `DEPROI_SSH_KEY` e `DEPROI_KNOWN_HOSTS` no GitHub environment. Quando diz que a conexão caiu, o deploy terminou no servidor: leia o resultado no syslog.

## Recusas comuns

| Mensagem | Causa | Correção (no servidor) |
|---|---|---|
| "alteração local em …" | Alguém editou arquivos rastreados no checkout. | `sudo -u <owner> git -C <checkout> diff`, depois faça commit deles em outro lugar ou `git checkout -- <file>`. |
| "está na branch X, não na Y" | Trocaram a branch do checkout. | `sudo -u <owner> git -C <checkout> switch <branch>` |
| "tem commit que não está em origin" | Alguém fez commit no servidor. | Faça push desses commits a partir do servidor, ou tire-os do caminho. |
| "arquivo não rastreado no caminho" | Um arquivo novo do commit já existe, não rastreado, no servidor. | Tire o arquivo não rastreado do caminho. |
| "aponta para o projeto X" | O arquivo env do commit indica outro projeto. | Corrija `COMPOSE_PROJECT_NAME` no commit. |
| "sem o sufixo" | Falta `profiles:` ou o sufixo num serviço. | Corrija o `compose.yaml` no commit. |
| "não tem healthcheck" | Não há `healthcheck:` nem `HEALTHCHECK`. | Adicione um ([contrato do projeto](project-contract.pt-BR.md)). |
| "Outro deploy está rodando…" | O deploy anterior ainda está rodando (ou travou). | Espere, ou confira `ps aux | grep deproi` no servidor. |

## Logs no servidor

```bash
journalctl -t deproi-myapp-prod -n 50            # inícios, resultados, pós-deploy
journalctl -t deproi-myapp-prod | grep 'result:'  # histórico de resultados
sudo docker logs --tail 100 myapp-prod-web-prod-1
sudo docker ps -a --filter label=com.docker.compose.project=myapp-prod
```

O `docker logs <container>` não precisa de arquivo env. Nos comandos `docker compose`, passe os mesmos arquivos que o Deproi usa (`--env-file deploy/prod.compose.env --env-file /etc/deproi/myapp-prod.secrets.env --profile prod`), senão as variáveis do arquivo de segredos saem vazias.

Depois de uma reversão, os contêineres da versão nova somem, mas a imagem construída fica: `docker image ls myapp`.

## Rodar um deploy de novo

**Actions → Deploy production → Run workflow** publica de novo o último commit da branch (útil depois de mudar a configuração ou os segredos do servidor). No servidor: `sudo /usr/local/sbin/deproi-myapp-prod`.

Publicar de novo o mesmo commit recria à força os serviços do próprio projeto (os que rodam a sua imagem), para que eles peguem os segredos novos. Os serviços de terceiros, como o banco de dados, continuam rodando, e os serviços protegidos ocupados seguem as regras de sempre.

## Pausar os deploys

Crie a variável `DEPROI_PAUSED` = `true` no GitHub environment. Os pushes continuam disparando o workflow, que só escreve "paused" e não se conecta a nada. Apague a variável para retomar.

## Plano B: deploy à mão

Quando o Deproi não consegue se recuperar (`FAILED_ROLLBACK`), publique você mesmo uma versão que sabidamente funciona:

```bash
cd /srv/myapp-prod
sudo docker image ls myapp                             # escolha uma tag que funcionou (12 caracteres hexadecimais)
sudo env DEPROI_TAG=<tag> docker compose -p myapp-prod --env-file deploy/prod.compose.env \
     --env-file /etc/deproi/myapp-prod.secrets.env --profile prod up -d web-prod
sudo docker ps --filter label=com.docker.compose.project=myapp-prod
```

Diga quais serviços trazer de volta (aqui, `web-prod`), para que um worker protegido ocupado não seja recriado no meio de uma tarefa. Tire o `--env-file` dos segredos se o ambiente não tiver nenhum.

Depois corrija a branch. O próximo push faz o deploy normalmente.

## Trocar a chave de deploy

Rode de novo o `create-deploy-key.sh` (💻) e o `prepare-server.sh --public-key` com a chave pública nova (🖥️). A linha da chave antiga é substituída e o segredo no GitHub é sobrescrito.

## Atualizar o Deproi

Substitua o `deploy/deproi.py` pela nova release (ou faça merge do pull request aberto pelo `deproi-update.yml`) e faça push. O próximo deploy de cada ambiente a instala sozinho (`script=updated:…`). Leia as notas da release antes: elas listam qualquer chave de configuração nova.

O pull request do atualizador começa sem checks, porque o GitHub não roda workflows em pull requests abertos com o token do próprio workflow. Se a `main` exige checks, feche e reabra o pull request: isso faz eles rodarem.

## Conferir um ambiente

```bash
sudo ./doctor.sh --name myapp-prod
```

Só leitura: o comando instalado, a configuração, o checkout (branch, alterações locais, acesso ao fetch), as permissões dos segredos, a regra do sudo, a linha da chave, o Docker, o espaço livre e os últimos resultados.

## Monitores do Better Stack que ficaram com folga

Se um deploy morre enquanto os monitores estão com a folga, o próximo deploy os restaura primeiro. Para restaurar à mão, os valores originais estão em `/var/lib/deproi/<name>/monitors.json`.
