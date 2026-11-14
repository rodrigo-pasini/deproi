[🇺🇸 English](CONTRIBUTING.md) · 🇧🇷 Português

# Contribuindo com o Deproi

## Regras básicas

Elas protegem o modelo de segurança. Uma mudança que quebre alguma delas não é aceita, por mais conveniente que seja.

1. **O workflow do GitHub não carrega lógica de deploy.** Ele só abre a conexão SSH.
2. **O `deproi.py` não aceita argumentos.** O ambiente vem do caminho instalado; todo o resto vem da configuração com dono root no servidor. Nada do repositório, do cliente SSH ou do ambiente escolhe o alvo.
3. **Só biblioteca padrão, sintaxe de Python 3.10.** O script roda no `/usr/bin/python3` do servidor. Os testes garantem as duas coisas.
4. **Nenhuma GitHub Action de terceiros** no caminho do deploy.
5. **Nunca descartar trabalho no servidor.** Nada de `git reset`, `git clean` ou `git stash` no deployer.
6. **Integrações nunca mudam o desfecho do deploy.** Um notificador que falha é um aviso, nunca um deploy falho.

## Documentação em dois idiomas

- O inglês é a fonte da verdade. Todo `*.md` tem um par `*.pt-BR.md` ao lado.
- A primeira linha de cada arquivo é o seletor de idioma, com link para o par.
- Os dois arquivos mantêm os mesmos títulos, blocos de código e imagens. Traduza o texto, não a estrutura.
- Um PR que muda um doc em inglês atualiza o par pt-BR no mesmo PR.
- `python tools/check_docs_parity.py` confere tudo isso, e a CI o executa.

## Desenvolvimento

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
python tools/check_docs_parity.py
```

## Commits e pull requests

- PRs pequenos e focados. Descreva a mudança de comportamento e como ela foi testada.
- Atualize o `CHANGELOG.md` e o `CHANGELOG.pt-BR.md` em *Não lançado*.
