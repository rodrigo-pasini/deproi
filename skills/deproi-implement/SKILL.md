---
name: deproi-implement
description: Set up Deproi (automatic deploys from GitHub to your own server over a locked-down SSH key, with Docker Compose, health checks and automatic rollback) in the current project, upgrade Deproi in a project that uses it, or explain a failed Deproi deploy. Use when the user asks to "add automatic deploy", "set up Deproi", "deploy on push to my server", "upgrade Deproi", or pastes a Deproi `result:` line.
---

# Deproi — implement, upgrade, troubleshoot

Deproi's instructions for agents live in one place: its `AGENTS.md`. This skill only makes sure you read the right version of it before acting.

1. Find the latest release: `gh api repos/rodrigo-pasini/deproi/releases/latest --jq .tag_name` (or <https://github.com/rodrigo-pasini/deproi/releases>). If the project already has `deploy/deproi.py`, also note its `DEPROI_VERSION`.
2. Read the whole `AGENTS.md` of that tag:
   `curl -fsSL https://raw.githubusercontent.com/rodrigo-pasini/deproi/<tag>/AGENTS.md`
3. Follow the section that matches the request — implementing, upgrading or reading a failed deploy — literally, including its rules R1–R9:
   never put logic in the workflow, never weaken the server side, never put secrets in the repository, never edit `deproi.py`, never run server or GitHub-secret commands yourself unless the user explicitly asks, never guess infrastructure values, pin the release.
4. Ask the user the questionnaire from `AGENTS.md` in one message before changing infrastructure-related files, and answer in the user's language.
5. End with the handover message from `AGENTS.md`, filled in, and ask for the evidence it lists (doctor output, `result:` lines).
