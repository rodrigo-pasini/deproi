🇺🇸 English · [🇧🇷 Português](README.pt-BR.md)

# Deproi

**Simple automatic deployer.** Push to a branch and your Docker Compose app is rebuilt, migrated, recreated and health-checked on your own server, with automatic rollback when the new version is not healthy.

> 🚧 **Work in progress.** Deproi is being extracted from a deployer that runs in production today. Until `v1.0.0` this README describes the goal, not a finished product. Follow the [changelog](CHANGELOG.md).

## The idea in one line

```text
git push → GitHub Actions → ssh (key locked to one command) → sudo deproi → docker compose → healthy? ✅ : rollback ↩️
```

## Why Deproi

- **Your server, your containers.** No platform, no agent running on the server, no third-party GitHub Actions.
- **The workflow carries no deploy logic.** The SSH key can run exactly one command, and that command lives on the server, owned by root. Changing the YAML does not change what runs with privilege.
- **Safe by default.** Fast-forward-only checkout, a lock per environment, a disk space check, health check, automatic rollback, and machine-readable results.
- **Generic.** Any stack that runs in Docker Compose with a health check. Migrations and other steps are configurable hooks.

## Status

| Area | State |
|---|---|
| Repository skeleton, CI, docs parity | ✅ |
| Core deployer (`deproi.py`) | ⏳ |
| Optional integrations (Better Stack, Cloudflare, webhook) | ⏳ |
| Server setup scripts and templates | ⏳ |
| End-to-end example | ⏳ |
| Visual guide | ⏳ |
| Guide for AI agents | ⏳ |

## Documentation in two languages

Every document is written in English and has a Brazilian Portuguese twin next to it (`*.pt-BR.md`). CI fails if a twin is missing or out of structure.

## For AI agents

Start with [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE).
