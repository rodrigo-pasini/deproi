[🇺🇸 English](AGENTS.md) · 🇧🇷 Português

# AGENTS.md — instruções para agentes de IA

> Esta é a tradução para humanos revisarem. Agentes: leiam o [AGENTS.md](AGENTS.md), em inglês.

Leia este arquivo antes de fazer qualquer coisa neste repositório. Responda ao humano no idioma dele.

## Qual tarefa você está fazendo?

| Pediram para você… | Vá para |
|---|---|
| **Adicionar o Deproi a outro projeto** | [Implantar o Deproi num projeto](#implantar-o-deproi-num-projeto) |
| **Mudar o próprio Deproi** (este repositório) | [Trabalhar neste repositório](#trabalhar-neste-repositório) |

## Implantar o Deproi num projeto

> 🚧 O guia de implantação ainda não foi escrito (chega antes da `v1.0.0`). **Não tente implantar o Deproi num projeto a partir do estado atual deste repositório.** Avise o humano que ainda não está pronto.

## Trabalhar neste repositório

1. Siga todas as regras do [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md#regras-básicas). Elas são o modelo de segurança, não preferências de estilo.
2. Toda mudança de documentação é feita **nos dois** idiomas na mesma mudança: primeiro o arquivo em inglês, depois o par `*.pt-BR.md` com a mesma estrutura. Rode `python tools/check_docs_parity.py`.
3. O `deproi.py` continua um **arquivo único**, só com a biblioteca padrão, válido em Python 3.10. A autoatualização instala exatamente um arquivo.
4. Antes de terminar, rode `ruff check .`, `ruff format --check .`, `pytest` e a checagem de paridade, e reporte os resultados reais.
5. Nunca adicione linhas de coautoria ou de atribuição a IA nos commits.
