"""Parity with the deployer Deproi was extracted from (validation layer 1).

The origin deployer is a private, production-tested script. It is NOT part of
this repository. These tests run only when ``DEPROI_ORIGIN_SCRIPT`` points to
a local copy of it; every name they use (branch, project, services, image) is
read from that script at run time, so nothing private is committed here.

Both deployers run the same scenarios against equivalent fake executors. The
core behaviour must match: the git sequence (exact), the order of build →
recreate, the number of recreations (rollback), the exit code, and that a
refusal touches no service.

    DEPROI_ORIGIN_SCRIPT=/path/to/origin_deploy.py pytest tests/test_origin_parity.py -v
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from conftest import Clock, FakeExecutor, make_config

import deproi

ORIGIN = os.environ.get("DEPROI_ORIGIN_SCRIPT", "")
pytestmark = pytest.mark.skipif(
    not ORIGIN or not Path(ORIGIN).is_file(), reason="DEPROI_ORIGIN_SCRIPT not set (origin deployer is private)"
)

COMMIT = "abc123def456"
PREVIOUS = "111111111111"


@pytest.fixture(scope="module")
def origin():
    spec = importlib.util.spec_from_file_location("origin_deploy", ORIGIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules["origin_deploy"] = module
    spec.loader.exec_module(module)
    # The first environment of the origin's table (its test environment).
    name = next(iter(module.AMBIENTES))
    module.aplicar_ambiente(name)
    return module


class OriginExecutor:
    """The origin's executor API (``rodar``/``Resultado``) over a response table."""

    def __init__(self, module, responses):
        self.module = module
        self.responses = responses
        self.calls = []

    def rodar(self, comando, *, cwd=None, ambiente=None, capturar=False, timeout=None, ecoar=False):
        comando = list(comando)
        self.calls.append(comando)
        text = " ".join(comando)
        for key, (code, output) in self.responses.items():
            if key in text:
                if isinstance(output, list):
                    output = output.pop(0) if len(output) > 1 else output[0]
                return self.module.Resultado(code, output)
        return self.module.Resultado(0, "")


def origin_responses(m, *, health="healthy", dirty="", project=None, build_code=0):
    script = Path(ORIGIN).read_bytes()
    return {
        "rev-parse --abbrev-ref HEAD": (0, m.BRANCH + "\n"),
        "status --porcelain": (0, dirty),
        f"show origin/{m.BRANCH}:{m.ARQUIVO_COMPOSE_ENV}": (0, f"COMPOSE_PROJECT_NAME={project or m.PROJETO}\n"),
        "merge-base --is-ancestor": (0, ""),
        "merge --ff-only": (0, ""),
        "rev-parse --short=12 HEAD": (0, COMMIT + "\n"),
        f"show {COMMIT}:{m.CAMINHO_NO_REPOSITORIO}": (0, script.decode()),
        f"rev-parse {COMMIT}:{m.CAMINHO_NO_REPOSITORIO}": (0, m.objeto_do_git(script) + "\n"),
        "config --services": (0, f"{m.SERVICO_WEB}\n"),
        "showmigrations": (0, "[X]  app.0001_initial\n"),
        # The origin's long-running worker is stopped: it is left alone (like a stopped protected service).
        "{{.State.Running}}": (0, "false\n"),
        "{{.Config.Image}}": (0, f"{m.IMAGEM}:{PREVIOUS}\n"),
        "{{.State.Health.Status}}": (0, health),
        " build ": (build_code, ""),
        "image ls": (0, f"{COMMIT}\n{PREVIOUS}\n"),
        "ps -a": (0, ""),
    }


def run_origin(m, tmp_path, **kwargs):
    installed = tmp_path / "origin-installed"
    installed.write_bytes(Path(ORIGIN).read_bytes())
    executor = OriginExecutor(m, origin_responses(m, **kwargs))
    clock = Clock()
    code = m.principal(
        [],
        executor,
        ambiente={},
        euid=lambda: 0,
        relogio=clock,
        dormir=clock.sleep,
        travar=lambda path, wait: 3,
        livre=lambda: 50 * 1024**3,
        config_betterstack=lambda: None,
        config_cloudflare=lambda: None,
        dir_estado=str(tmp_path / "s"),
        segundo_plano=lambda work: None,
        caminho_instalado=str(installed),
        carregar=lambda *a: (True, ""),
        executar=lambda *a: None,
        chown=lambda *a: None,
        em_uso=Path(ORIGIN).read_bytes(),
    )
    return code, executor.calls


def run_deproi(tmp_path, capsys, *, health="healthy\n", dirty="", project="myapp-prod", build_code=0):
    from conftest import Run

    responses = {
        "status --porcelain": deproi.Result(0, dirty),
        "show origin/main:deploy/prod.compose.env": deproi.Result(0, f"COMPOSE_PROJECT_NAME={project}\n"),
        "{{.State.Health.Status}}": health if isinstance(health, list) else deproi.Result(0, health),
        " build": deproi.Result(build_code, ""),
    }
    run = Run(tmp_path, capsys)
    run(FakeExecutor(first=responses), cfg=make_config(tmp_path))
    return run.code, run.executor.commands()


def core(calls) -> list:
    """The behaviour both deployers must share, as a sequence of operation kinds."""
    kinds = []
    for command in calls:
        text = " ".join(command)
        if command[:1] == ["logger"]:
            continue
        if " git -C " in f" {text} ":
            kinds.append("git:" + command[command.index("-C") + 2])
        elif " compose " in f" {text} " and (" build" in text):
            kinds.append("build")
        elif " compose " in f" {text} " and " up " in f" {text} " and "--remove-orphans" in text:
            kinds.append("up")
        elif command[:3] == ["docker", "image", "rm"]:
            kinds.append("image-rm")
    return kinds


UNHEALTHY_THEN_HEALTHY = 49  # the first health wait fails (240 s / 5 s + 1 checks), the rollback's is healthy

SCENARIOS = {
    "success": {},
    "dirty checkout": {"dirty": " M app.py\n"},
    "build failure": {"build_code": 1},
    "unhealthy, rollback healthy": {"rollback_healthy": True},
    "unhealthy, rollback unhealthy": {"health": "unhealthy\n"},
}


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_same_core_behaviour(origin, tmp_path, capsys, scenario):
    kwargs = dict(SCENARIOS[scenario])
    (tmp_path / "o").mkdir()
    (tmp_path / "d").mkdir()
    if kwargs.pop("rollback_healthy", False):
        origin_health = ["unhealthy\n"] * UNHEALTHY_THEN_HEALTHY + ["healthy\n"]
        deproi_health = [deproi.Result(0, "unhealthy\n")] * UNHEALTHY_THEN_HEALTHY + [deproi.Result(0, "healthy\n")]
        origin_code, origin_calls = run_origin(origin, tmp_path / "o", health=origin_health)
        deproi_code, deproi_calls = run_deproi(tmp_path / "d", capsys, health=deproi_health)
    else:
        origin_code, origin_calls = run_origin(origin, tmp_path / "o", **kwargs)
        deproi_code, deproi_calls = run_deproi(tmp_path / "d", capsys, **kwargs)
    assert deproi_code == origin_code, scenario
    assert core(deproi_calls) == core(origin_calls), scenario


def test_wrong_project_is_refused_by_both(origin, tmp_path, capsys):
    (tmp_path / "o").mkdir()
    (tmp_path / "d").mkdir()
    origin_code, origin_calls = run_origin(origin, tmp_path / "o", project="someone-else")
    deproi_code, deproi_calls = run_deproi(tmp_path / "d", capsys, project="someone-else")
    assert origin_code == deproi_code == 2
    assert "git:merge" not in core(origin_calls) and "git:merge" not in core(deproi_calls)
