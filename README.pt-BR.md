[🇺🇸 English](README.md) · 🇧🇷 Português

# Deproi

**Deployer simples automático.** Faça push numa branch e sua aplicação em Docker Compose é reconstruída, migrada, recriada e conferida no seu próprio servidor, com reversão automática quando a versão nova não fica saudável.

> 🚧 **Em construção.** O Deproi está sendo extraído de um deployer que roda hoje em produção. Até a `v1.0.0`, este README descreve o objetivo, não um produto pronto. Acompanhe o [changelog](CHANGELOG.pt-BR.md).

## A ideia em uma linha

```text
git push → GitHub Actions → ssh (chave presa a um comando) → sudo deproi → docker compose → saudável? ✅ : reverte ↩️
```

## Por que o Deproi

- **Seu servidor, seus contêineres.** Sem plataforma, sem agente rodando no servidor, sem GitHub Actions de terceiros.
- **O workflow não carrega lógica de deploy.** A chave SSH só executa um comando, e esse comando mora no servidor, com dono root. Mudar o YAML não muda o que roda com privilégio.
- **Seguro por padrão.** Checkout só por fast-forward, trava por ambiente, conferência de espaço em disco, healthcheck, reversão automática e resultado legível por máquina.
- **Genérico.** Qualquer stack que rode em Docker Compose com healthcheck. Migrations e outros passos são ganchos configuráveis.

## Situação

| Área | Estado |
|---|---|
| Esqueleto do repositório, CI, paridade das docs | ✅ |
| Núcleo do deployer (`deproi.py`) | ⏳ |
| Integrações opcionais (Better Stack, Cloudflare, webhook) | ⏳ |
| Scripts de preparação do servidor e templates | ⏳ |
| Exemplo de ponta a ponta | ⏳ |
| Guia visual | ⏳ |
| Guia para agentes de IA | ⏳ |

## Documentação em dois idiomas

Todo documento é escrito em inglês e tem o equivalente em português do Brasil ao lado (`*.pt-BR.md`). A CI falha se faltar o par ou se a estrutura divergir.

## Para agentes de IA

Comece pelo [AGENTS.pt-BR.md](AGENTS.pt-BR.md) (agentes: leiam o [AGENTS.md](AGENTS.md), em inglês).

## Licença

[MIT](LICENSE).
