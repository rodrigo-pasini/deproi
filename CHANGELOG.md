🇺🇸 English · [🇧🇷 Português](CHANGELOG.pt-BR.md)

# Changelog

All notable changes to Deproi are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Repository skeleton: MIT license, contribution guide, CI (lint, tests on Python 3.10 and 3.12, workflow lint, shell lint).
- Documentation parity check: every English doc must have a pt-BR twin with the same structure.
- `deproi.py`, the deployer: config in `/etc/deproi/<name>.json` (validated strictly, root-owned), lock, disk check, fast-forward-only checkout, self-update from the commit, Compose definition fence (project, service suffix, image tag), build, health check requirement, hooks (`pre_migrate`, `migrate`, `post_migrate`, `post_deploy`), protected services, recreate, health wait, automatic rollback with the previous definition, image cleanup, bilingual messages (en, pt-BR).
- Optional integrations: Better Stack (monitor grace period, release), Cloudflare cache purge, webhook (JSON, Slack, Discord).
- `deproi.schema.json` for editor autocomplete and validation.
- Test suite (210 tests, Python 3.10 and 3.12) and parity tests against the origin deployer (run locally).
