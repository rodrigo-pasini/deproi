[🇺🇸 English](CHANGELOG.md) · 🇧🇷 Português

# Changelog

Todas as mudanças relevantes do Deproi ficam registradas aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- Esqueleto do repositório: licença MIT, guia de contribuição, CI (lint, testes em Python 3.10 e 3.12, lint dos workflows e dos scripts shell).
- Checagem de paridade da documentação: todo doc em inglês precisa de um par pt-BR com a mesma estrutura.
- `deproi.py`, o deployer: configuração em `/etc/deproi/<nome>.json` (validada com rigor, dono root), trava, conferência de disco, checkout só por fast-forward, autoatualização pelo commit, cerca da definição do Compose (projeto, sufixo dos serviços, tag da imagem), build, exigência de healthcheck, ganchos (`pre_migrate`, `migrate`, `post_migrate`, `post_deploy`), serviços protegidos, recriação, espera da saúde, reversão automática com a definição anterior, limpeza de imagens, mensagens bilíngues (en, pt-BR).
- Integrações opcionais: Better Stack (folga nos monitores, release), purga do cache da Cloudflare, webhook (JSON, Slack, Discord).
- `deproi.schema.json` para autocomplete e validação no editor.
- Suíte de testes (210 testes, Python 3.10 e 3.12) e testes de paridade com o deployer de origem (rodam localmente).
