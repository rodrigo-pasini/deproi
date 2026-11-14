[🇺🇸 English](SECURITY.md) · 🇧🇷 Português

# Política de segurança

O Deproi roda como root no seu servidor, disparado pelo GitHub. Relatos de segurança são levados a sério e tratados primeiro.

## Reportar uma vulnerabilidade

**Não abra uma issue pública.** Use o relato privado do GitHub: [Report a vulnerability](https://github.com/rodrigo-pasini/deproi/security/advisories/new).

Inclua a versão do Deproi, o que o atacante precisa (acesso de push? a chave de deploy? um shell no servidor?), o que ele ganha e os passos para reproduzir. A primeira resposta vem em até 7 dias. As correções saem numa versão nova com um GitHub Security Advisory, e você recebe o crédito, a menos que peça o contrário.

## Versões suportadas

| Versão | Suportada |
|---|---|
| Última versão minor | ✅ |
| Versões anteriores | ❌ atualize primeiro |

## O modelo de segurança em resumo

- Quem consegue fazer push numa branch de deploy consegue rodar código como root naquele servidor, porque o Docker Compose executa os contêineres do projeto. Proteja as branches de deploy de acordo.
- A chave SSH de deploy só dispara o deploy (`restrict,command=`); ela não abre shell nem passa argumentos.
- O script de deploy e a configuração dele ficam fora do checkout, com dono root.

No escopo: tudo que permita ir além desse modelo, por exemplo rodar comandos arbitrários com a chave de deploy, escolher outro alvo ou ler segredos do servidor pela saída do deploy.
