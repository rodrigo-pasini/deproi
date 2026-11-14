🇺🇸 English · [🇧🇷 Português](CONTRIBUTING.pt-BR.md)

# Contributing to Deproi

## Ground rules

These protect the security model. A change that breaks one of them is not accepted, however convenient.

1. **The GitHub workflow carries no deploy logic.** It only opens the SSH connection.
2. **`deproi.py` accepts no arguments.** The environment comes from the installed path; everything else comes from the root-owned config on the server. Nothing from the repository, the SSH client or the environment selects the target.
3. **Standard library only, Python 3.10 syntax.** The script runs on the server's `/usr/bin/python3`. Tests enforce both.
4. **No third-party GitHub Actions** in the deploy path.
5. **Never discard work on the server.** No `git reset`, `git clean` or `git stash` in the deployer.
6. **Integrations never change the deploy outcome.** A failing notifier is a warning, never a failed deploy.

## Documentation in two languages

- English is the source of truth. Every `*.md` has a `*.pt-BR.md` twin next to it.
- The first line of each file is the language switcher, linking to the twin.
- Both files keep the same headings, code blocks and images. Translate the prose, not the structure.
- A PR that changes an English doc updates the pt-BR twin in the same PR.
- `python tools/check_docs_parity.py` checks all of this, and CI runs it.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
python tools/check_docs_parity.py
```

## Commits and pull requests

- Small, focused PRs. Describe the behaviour change and how it was tested.
- Update `CHANGELOG.md` and `CHANGELOG.pt-BR.md` under *Unreleased*.
