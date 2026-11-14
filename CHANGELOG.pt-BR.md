[🇺🇸 English](CHANGELOG.md) · 🇧🇷 Português

# Changelog

Todas as mudanças relevantes do Deproi ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.2.0] - 2026-11-14

### Adicionado

- `scripts/try-locally.sh`: ensaia o deploy de um projeto num contêiner servidor descartável, antes de mexer num servidor real.

### Alterado

- O deploy agora sobe os serviços de terceiros (banco, cache) que ainda não estão rodando, e espera que fiquem saudáveis, antes dos ganchos: as migrations funcionam já no primeiro deploy.
- A espera da saúde termina cedo quando o Docker reporta `unhealthy` três vezes seguidas, então uma versão quebrada é revertida em segundos, e não depois do timeout inteiro.
- Republicar o mesmo commit recria à força só os serviços do próprio projeto, nunca os de terceiros, como o banco.
- As releases incluem `prepare-server.sh`, `doctor.sh` e `create-deploy-key.sh` no `SHA256SUMS`; a documentação os confere antes de rodar. O atualizador confere o `deproi.py` com `--ignore-missing`.
- A configuração inicial escrita pelo `prepare-server.sh` fixa o `$schema` na versão instalada.

### Documentação

- Uma ordem de instalação que funciona: pausar os deploys, mergear, preparar o servidor, criar a chave, retomar. Acesso de fetch para o dono do checkout, `--port`, downloads conferidos.
- Migrar de um deploy existente (volumes, portas, órfãos, credenciais antigas); servidores compartilhados (portas, nomes de imagem); serviços protegidos (ordem, reversão, parada graciosa, política de restart); plano B e comandos de log corrigidos; receita para Node.js.
- Achados de duas implantações piloto feitas por agentes de IA (Django + Postgres, Node + Redis com worker protegido).

### Nota de atualização

- Projetos que renderizaram o `deproi-update.yml` da 0.1.0 precisam renderizá-lo de novo: o atualizador da 0.1.0 não consegue conferir releases cujo checksum cobre mais de um arquivo.

## [0.1.0] - 2026-11-14

### Adicionado

- Esqueleto do repositório: licença MIT, guia de contribuição, CI (lint, testes em Python 3.10 e 3.12, lint dos workflows e dos scripts shell).
- Checagem de paridade da documentação: todo doc em inglês precisa de um par pt-BR com a mesma estrutura.
- `deproi.py`, o deployer: configuração em `/etc/deproi/<nome>.json` (validada com rigor, dono root), trava, conferência de disco, checkout só por fast-forward, autoatualização pelo commit, cerca da definição do Compose (projeto, sufixo dos serviços, tag da imagem), build, exigência de healthcheck, ganchos (`pre_migrate`, `migrate`, `post_migrate`, `post_deploy`), serviços protegidos, recriação, espera da saúde, reversão automática com a definição anterior, limpeza de imagens, mensagens bilíngues (en, pt-BR).
- Integrações opcionais: Better Stack (folga nos monitores, release), purga do cache da Cloudflare, webhook (JSON, Slack, Discord).
- `deproi.schema.json` para autocomplete e validação no editor.
- Ferramentas para servidor e GitHub: `prepare-server.sh` (usuário, regra do sudo validada com visudo, comando instalado, configuração inicial, linha da chave presa), `doctor.sh` (conferências só de leitura), `create-deploy-key.sh` (chave, conferência da impressão digital do host, environment e segredos no GitHub, chave apagada da máquina), `render-workflow.sh`.
- Templates de workflow: o workflow de deploy (sem lógica, segredos no GitHub environment, interruptor de pausa, resumo) e o `deproi-update.yml` opcional, que abre um pull request para novas versões do Deproi depois de conferir o SHA256SUMS.
- Workflow de release que publica o `deproi.py` e o `SHA256SUMS`.
- Suíte de testes (210 testes, Python 3.10 e 3.12) e testes de paridade com o deployer de origem (rodam localmente).
- Projeto de exemplo (`example/`) e um teste de ponta a ponta (`tests/e2e/run.sh`) que o implanta por SSH num contêiner servidor: sucesso, commit novo, chave presa, reversão, serviço protegido ocupado, autoatualização, recusas; roda na CI.
- Documentação em inglês e português do Brasil: README com diagramas animados (fluxo, reversão, camadas de segurança, um log real de deploy), como funciona, instalação, contrato do projeto, configuração, receitas, integrações, operação, segurança.
- `AGENTS.md`: o guia para agentes de IA implantarem, atualizarem ou investigarem o Deproi num projeto; uma skill do Claude Code que aponta para ele.

### Corrigido

- Um serviço protegido que ainda não tem contêiner (primeiro deploy) é criado, em vez de ser tratado como parado.
- `prepare-server.sh` e `doctor.sh` detectam um usuário `deproi` que consegue escrever no socket do Docker por qualquer grupo, não só um chamado `docker`.
- A URL de um webhook nunca aparece em linhas de erro (só o host).
