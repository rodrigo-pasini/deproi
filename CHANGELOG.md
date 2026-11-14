🇺🇸 English · [🇧🇷 Português](CHANGELOG.pt-BR.md)

# Changelog

All notable changes to Deproi are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-14

### Added

- Repository skeleton: MIT license, contribution guide, CI (lint, tests on Python 3.10 and 3.12, workflow lint, shell lint).
- Documentation parity check: every English doc must have a pt-BR twin with the same structure.
- `deproi.py`, the deployer: config in `/etc/deproi/<name>.json` (validated strictly, root-owned), lock, disk check, fast-forward-only checkout, self-update from the commit, Compose definition fence (project, service suffix, image tag), build, health check requirement, hooks (`pre_migrate`, `migrate`, `post_migrate`, `post_deploy`), protected services, recreate, health wait, automatic rollback with the previous definition, image cleanup, bilingual messages (en, pt-BR).
- Optional integrations: Better Stack (monitor grace period, release), Cloudflare cache purge, webhook (JSON, Slack, Discord).
- `deproi.schema.json` for editor autocomplete and validation.
- Server and GitHub tooling: `prepare-server.sh` (user, sudo rule validated with visudo, installed command, starter config, locked key line), `doctor.sh` (read-only checks), `create-deploy-key.sh` (key, host fingerprint check, GitHub environment and secrets, key deleted locally), `render-workflow.sh`.
- Workflow templates: the deploy workflow (no logic, GitHub environment secrets, pause switch, summary) and the optional `deproi-update.yml` that opens a pull request for new Deproi releases after verifying SHA256SUMS.
- Release workflow publishing `deproi.py` and `SHA256SUMS`.
- Test suite (210 tests, Python 3.10 and 3.12) and parity tests against the origin deployer (run locally).
- Example project (`example/`) and an end-to-end test (`tests/e2e/run.sh`) that deploys it over SSH into a server container: success, new commit, locked key, rollback, busy protected service, self-update, refusals; runs in CI.
- Documentation in English and Brazilian Portuguese: README with animated diagrams (pipeline, rollback, security layers, a real deploy log), how it works, installation, project contract, configuration, recipes, integrations, operations, security.
- `AGENTS.md`: the guide for AI agents implementing, upgrading or troubleshooting Deproi in a project; a Claude Code skill that points to it.

### Fixed

- A protected service with no container yet (first deploy) is created instead of being treated as stopped.
- `prepare-server.sh` and `doctor.sh` detect a `deproi` user that can write the Docker socket through any group, not only one named `docker`.
- A webhook URL never appears in error lines (only its host).
