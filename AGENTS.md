🇺🇸 English · [🇧🇷 Português](AGENTS.pt-BR.md)

# AGENTS.md — instructions for AI agents

Read this file before doing anything in this repository. Answer the human in the human's language.

## Which task are you doing?

| You were asked to… | Go to |
|---|---|
| **Add Deproi to another project** | [Implementing Deproi in a project](#implementing-deproi-in-a-project) |
| **Change Deproi itself** (this repository) | [Working on this repository](#working-on-this-repository) |

## Implementing Deproi in a project

> 🚧 The implementation guide is not written yet (it arrives before `v1.0.0`). **Do not try to implement Deproi in a project from the current state of this repository.** Tell the human it is not ready yet.

## Working on this repository

1. Follow every rule in [CONTRIBUTING.md](CONTRIBUTING.md#ground-rules). They are the security model, not style preferences.
2. Every documentation change is made in **both** languages in the same change: the English file first, then the `*.pt-BR.md` twin with the same structure. Run `python tools/check_docs_parity.py`.
3. `deproi.py` stays a **single file**, standard library only, valid Python 3.10. Its self-update installs exactly one file.
4. Before finishing, run `ruff check .`, `ruff format --check .`, `pytest` and the parity check, and report the real results.
5. Never add co-author or AI attribution lines to commits.
