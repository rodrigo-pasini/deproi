"""Shared fixtures for the deproi.py suite.

The script runs on a server as root. These tests touch no Docker, git,
network, /etc or /var: the command executor is a fake that records every call
and answers from a table of canned responses.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import deproi

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = (ROOT / "deproi.py").read_bytes()
COMMIT = "abc123def456"
PREVIOUS = "111111111111"
WEB_ID = "a" * 12
WORKER_ID = "b" * 12
GB = 1024**3
COMPOSE_ENV = "# comment\nCOMPOSE_PROJECT_NAME=myapp-prod\nDEPROI_TAG=local\n"

BASE_CONFIG = {
    "name": "myapp-prod",
    "language": "en",
    "checkout": {"path": "/srv/myapp", "owner": "deployer", "branch": "main"},
    "compose": {
        "project": "myapp-prod",
        "env_file": "deploy/prod.compose.env",
        "secrets_file": "/etc/deproi/myapp-prod.secrets.env",
        "profiles": ["prod"],
        "service_suffix": "-prod",
        "web_service": "web-prod",
        "image": "myapp",
    },
    "url": "https://app.example.com",
}


def definition(commit: str = COMMIT, *, web_health: bool = True, extra: dict | None = None) -> str:
    services = {
        "web-prod": {"image": f"myapp:{commit}", "build": {"context": "."}},
        "worker-prod": {"image": f"myapp:{commit}"},
        "redis-prod": {"image": "redis:7"},
    }
    if web_health:
        services["web-prod"]["healthcheck"] = {"test": ["CMD", "true"]}
    services.update(extra or {})
    return json.dumps({"name": "myapp-prod", "services": services})


def make_config(tmp_path, overrides: dict | None = None, **kwargs) -> deproi.Config:
    data = copy.deepcopy(BASE_CONFIG)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    return deproi.parse_config(
        data,
        "myapp-prod",
        state_root=str(tmp_path / "state"),
        lock_dir=str(tmp_path / "lock"),
        home_of=lambda user: f"/home/{user}",
        **kwargs,
    )


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeExecutor:
    """Records calls; answers by the first key found in the command text.

    A response is a ``Result`` or a list of them, consumed in order (the last one repeats).
    """

    def __init__(self, responses=None, *, first=None):
        self.calls = []
        self.responses = {
            # Most specific first.
            "rev-parse --abbrev-ref HEAD": deproi.Result(0, "main\n"),
            "status --porcelain": deproi.Result(0, ""),
            "show origin/main:deploy/prod.compose.env": deproi.Result(0, COMPOSE_ENV),
            "merge-base --is-ancestor": deproi.Result(0, ""),
            "merge --ff-only": deproi.Result(0, "Already up to date.\n"),
            "rev-parse --short=12 HEAD": deproi.Result(0, COMMIT + "\n"),
            f"show {COMMIT}:deploy/deproi.py": deproi.Result(0, SCRIPT.decode("utf-8")),
            f"rev-parse {COMMIT}:deploy/deproi.py": deproi.Result(0, deproi.git_blob_id(SCRIPT) + "\n"),
            f"show {PREVIOUS}:compose.yaml": deproi.Result(0, "services: {}\n"),
            f"show {PREVIOUS}:deploy/prod.compose.env": deproi.Result(0, COMPOSE_ENV),
            "config --format json": deproi.Result(0, definition()),
            "com.docker.compose.service=web-prod": deproi.Result(0, WEB_ID + "\n"),
            "com.docker.compose.service=worker-prod": deproi.Result(0, WORKER_ID + "\n"),
            "{{.Config.Image}}": deproi.Result(0, f"myapp:{PREVIOUS}\n"),
            "{{.State.Health.Status}}": deproi.Result(0, "healthy\n"),
            "{{.State.Running}}": deproi.Result(0, "true\n"),
            "image ls": deproi.Result(0, f"{COMMIT}\n{PREVIOUS}\n"),
            "--format {{.Image}}": deproi.Result(0, f"myapp:{COMMIT}\n"),
        }
        self.responses.update(responses or {})
        if first:
            self.responses = {**first, **{k: v for k, v in self.responses.items() if k not in first}}

    def run(self, command, *, cwd=None, env=None, capture=False, timeout=None, echo=False):
        command = list(command)
        assert all(isinstance(part, str) for part in command), command
        self.calls.append(
            SimpleNamespace(command=command, cwd=cwd, env=dict(env or {}), capture=capture, timeout=timeout, echo=echo)
        )
        text = " ".join(command)
        for key, response in self.responses.items():
            if key in text:
                if isinstance(response, list):
                    return response.pop(0) if len(response) > 1 else response[0]
                return response
        return deproi.Result(0, "")

    def commands(self, fragment: str = "") -> list:
        return [c.command for c in self.calls if fragment in " ".join(c.command)]

    def texts(self, fragment: str = "") -> list:
        return [" ".join(c) for c in self.commands(fragment)]

    def call(self, fragment: str):
        return next(c for c in self.calls if fragment in " ".join(c.command))


class Run:
    """Runs ``deproi.main`` with everything injected; keeps what the test wants to inspect."""

    def __init__(self, tmp_path, capsys):
        self.tmp_path = tmp_path
        self.capsys = capsys
        self.background = []
        self.executed = []
        installed = tmp_path / "sbin" / "deproi-myapp-prod"
        installed.parent.mkdir(exist_ok=True)
        installed.write_bytes(SCRIPT)
        self.installed = str(installed)

    def __call__(
        self,
        executor=None,
        *,
        cfg=None,
        overrides=None,
        argv=(),
        environ=None,
        euid=0,
        lock=3,
        free=50 * GB,
        clock=None,
        integrations=None,
        load=None,
        in_use=SCRIPT,
        config_error=None,
    ):
        self.executor = executor or FakeExecutor()
        self.cfg = cfg or make_config(self.tmp_path, overrides)
        self.clock = clock or Clock()

        def loader(name):
            if config_error:
                raise deproi.ConfigError(config_error)
            return self.cfg

        def execute(program, args, environ):
            self.executed.append((program, args, dict(environ)))

        self.code = deproi.main(
            list(argv),
            "myapp-prod",
            executor=self.executor,
            environ={} if environ is None else environ,
            euid=lambda: euid,
            clock=self.clock,
            sleep=self.clock.sleep,
            lock=lambda path, wait: lock,
            free=lambda: free,
            config_loader=loader,
            integrations=integrations or (lambda c, e: deproi.Integrations(c, e, opener=no_network, stat_fn=root_stat)),
            background=lambda work, c: self.background.append(work),
            installed=self.installed,
            load=load or (lambda path, executor: (True, "")),
            execute=execute,
            chown=lambda path, uid, gid: None,
            in_use=in_use,
        )
        self.out = self.capsys.readouterr().out
        return self

    @property
    def result(self) -> str:
        return next(line for line in reversed(self.out.splitlines()) if line.startswith("result: "))

    @property
    def message(self) -> str:
        return next(line for line in reversed(self.out.splitlines()) if line.startswith("message: "))[9:]

    def line(self, prefix: str) -> str:
        return next(line for line in self.out.splitlines() if line.startswith(prefix))


def recreates(executor) -> list:
    """The ``up`` commands that recreate services (not the dependencies' ``up --no-recreate``)."""
    return [c for c in executor.commands(" up ") if "--no-recreate" not in c]


def no_network(*args, **kwargs):
    raise AssertionError("a test tried to reach the network")


def root_stat(path):
    """A stat that says every file is root-owned with safe permissions."""
    return SimpleNamespace(st_uid=0, st_mode=0o100600 if not os.path.isdir(path) else 0o040755)


@pytest.fixture
def run(tmp_path, capsys):
    return Run(tmp_path, capsys)


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    """No test reaches the network, re-executes the process or reads the real config."""
    monkeypatch.setattr(deproi.urllib.request, "urlopen", no_network)
    monkeypatch.setattr(deproi, "reexecute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("execve")))
    monkeypatch.setattr(deproi, "peek_language", lambda name, config_dir=deproi.CONFIG_DIR: "en")
    monkeypatch.setattr(deproi, "LANGUAGE", "en")
    deproi._broken_output = False
