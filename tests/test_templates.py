"""Templates and scripts stay consistent with deproi.py and with each other."""

from __future__ import annotations

import json
import re
import subprocess

import pytest
from conftest import ROOT

import deproi

TEMPLATES = ROOT / "templates"
SCRIPTS = ROOT / "scripts"


def render(*args) -> str:
    return subprocess.run(
        [str(SCRIPTS / "render-workflow.sh"), *args], capture_output=True, text=True, check=True
    ).stdout


class TestDeployWorkflow:
    TEXT = render("deploy", "--name", "myapp-prod", "--branch", "main", "--environment", "production")

    def test_all_placeholders_are_replaced(self):
        assert "__DEPROI_" not in self.TEXT

    def test_carries_no_logic_and_no_third_party_actions(self):
        assert "permissions: {}" in self.TEXT
        assert "uses:" not in self.TEXT
        ssh = self.TEXT[self.TEXT.index("ssh -i") : self.TEXT.index("| tee")]
        assert '"$DEPROI_SSH_USER@$DEPROI_HOST"' in ssh
        # No remote command after the destination: the forced command decides.
        assert ssh.rstrip().endswith('"$DEPROI_SSH_USER@$DEPROI_HOST"')

    def test_strict_host_key_checking(self):
        for option in ("StrictHostKeyChecking=yes", "BatchMode=yes", "IdentitiesOnly=yes"):
            assert option in self.TEXT

    def test_runs_only_for_its_branch_and_environment(self):
        assert "if: github.ref == 'refs/heads/main'" in self.TEXT
        assert "environment: production" in self.TEXT
        assert "group: deproi-myapp-prod" in self.TEXT and "cancel-in-progress: false" in self.TEXT

    def test_summary_reads_the_lines_deproi_prints(self):
        assert "grep '^result: '" in self.TEXT and "grep '^message: '" in self.TEXT
        prefixes = re.search(r"grep -E '\^\(([a-z_|]+)\): '", self.TEXT).group(1).split("|")
        source = (ROOT / "deproi.py").read_text()
        for prefix in prefixes:
            assert f'"{prefix}: ' in source or f'f"{prefix}: ' in source, prefix
        assert len(prefixes) == 4

    @pytest.mark.parametrize("bad", [["--name", "Bad Name"], ["--branch", "main;rm"], ["--environment", "a b"]])
    def test_render_rejects_unsafe_values(self, bad):
        args = {"--name": "x", "--branch": "main", "--environment": "prod"}
        args[bad[0]] = bad[1]
        flat = [part for pair in args.items() for part in pair]
        result = subprocess.run(
            [str(SCRIPTS / "render-workflow.sh"), "deploy", *flat], capture_output=True, check=False
        )
        assert result.returncode == 2


class TestUpdateWorkflow:
    TEXT = render("update", "--script-path", "ops/deproi.py")

    def test_script_path(self):
        assert "SCRIPT: ops/deproi.py" in self.TEXT and "__DEPROI_" not in self.TEXT

    def test_verifies_checksums_and_only_opens_a_pull_request(self):
        assert "sha256sum --check --strict --ignore-missing SHA256SUMS" in self.TEXT
        assert "gh pr create" in self.TEXT
        assert "ssh" not in self.TEXT

    def test_only_first_party_actions_pinned_by_sha(self):
        for uses in re.findall(r"uses: (\S+)", self.TEXT):
            assert uses.startswith("actions/") and re.search(r"@[0-9a-f]{40}$", uses), uses

    def test_version_line_format_matches_deproi(self):
        assert 'DEPROI_VERSION = "' in (ROOT / "deproi.py").read_text()
        assert r'^DEPROI_VERSION = "\(.*\)"$' in self.TEXT


class TestServerFiles:
    PREPARE = (SCRIPTS / "prepare-server.sh").read_text()

    def rule_lines(self, text: str, name: str) -> list:
        lines = [line for line in text.splitlines() if line and not line.startswith("#")]
        return [
            line.replace("__DEPROI_NAME__", name)
            .replace("$COMMAND", f"/usr/local/sbin/deproi-{name}")
            .replace("$DEPLOY_USER", "deproi")
            for line in lines
        ]

    def test_sudoers_rule_matches_the_template(self):
        template = self.rule_lines((TEMPLATES / "server" / "sudoers.template").read_text(), "x")
        heredocs = [part.split("\nEOF")[0] for part in self.PREPARE.split('cat > "$temporary" << EOF\n')[1:]]
        heredoc = next(text for text in heredocs if "NOPASSWD" in text)
        assert self.rule_lines(heredoc, "x") == template

    def test_sudoers_forbids_arguments(self):
        assert re.search(r'NOPASSWD: \S+ ""$', (TEMPLATES / "server" / "sudoers.template").read_text(), re.M)

    def test_authorized_keys_line_matches_the_template(self):
        template = next(
            line
            for line in (TEMPLATES / "server" / "authorized_keys.template").read_text().splitlines()
            if line.startswith("restrict")
        )
        printf = re.search(r"printf '(restrict[^']+)\\n'", self.PREPARE).group(1)
        expected = (
            template.replace("/usr/local/sbin/deproi-__DEPROI_NAME__", "%s")
            .replace("__PUBLIC_KEY__", "%s")
            .replace("__DEPROI_NAME__", "%s")
        )
        assert printf == expected

    def test_doctor_checks_the_same_rules(self):
        doctor = (SCRIPTS / "doctor.sh").read_text()
        assert 'NOPASSWD: $COMMAND \\"\\"\\$' in doctor
        assert 'restrict,command=\\"sudo -n $COMMAND\\" ssh-ed25519' in doctor

    def test_example_config_is_valid(self):
        data = json.loads((TEMPLATES / "server" / "deproi.example.json").read_text())
        cfg = deproi.parse_config(data, "myapp-prod", home_of=lambda user: "/home/x")
        assert cfg.hooks["migrate"][0].command[-1] == "--noinput"

    def test_starter_config_written_by_prepare_server_is_valid(self):
        heredoc = self.PREPARE.split('cat > "$temporary" << EOF\n{')[1].split("\nEOF")[0]
        text = "{" + heredoc.replace("\\$schema", "$schema").replace("$VERSION", "0.2.0").replace(
            "$NAME", "myapp-prod"
        ).replace("$CHECKOUT", "/srv/myapp-prod").replace("$OWNER", "ubuntu")
        cfg = deproi.parse_config(json.loads(text), "myapp-prod", home_of=lambda user: "/home/x")
        assert cfg.web_service == "web"

    @pytest.mark.parametrize("name", ["betterstack", "cloudflare", "webhook"])
    def test_credential_examples_use_the_keys_deproi_reads(self, name):
        keys = re.findall(r"^([A-Z_]+)=", (TEMPLATES / "server" / f"{name}.env.example").read_text(), re.M)
        source = (ROOT / "deproi.py").read_text()
        assert keys and all(f'"{key}"' in source for key in keys)


@pytest.mark.parametrize("script", sorted(p.name for p in SCRIPTS.glob("*.sh")))
def test_scripts_are_strict_and_executable(script):
    path = SCRIPTS / script
    text = path.read_text()
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text or "set -uo pipefail" in text
    assert path.stat().st_mode & 0o111
