"""Protected services (long-running workers) and the self-update from the commit."""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys

import pytest
from conftest import COMMIT, PREVIOUS, ROOT, SCRIPT, WORKER_ID, FakeExecutor, recreates

import deproi

R = deproi.Result

PROTECTED = {
    "protected_services": [
        {
            "service": "worker-prod",
            "busy_check": ["worker", "busy"],
            "quiesce": ["worker", "pause"],
            "resume": ["worker", "resume"],
        }
    ]
}


def ups(executor):
    return recreates(executor)


class TestProtectedServices:
    def test_idle_service_is_quiesced_checked_again_and_recreated_after_the_rest(self, run):
        run(overrides=PROTECTED)
        assert run.code == 0
        execs = [c[2:] for c in run.executor.commands("docker exec")]
        assert execs == [[WORKER_ID, "worker", "busy"], [WORKER_ID, "worker", "pause"], [WORKER_ID, "worker", "busy"]]
        first, second = ups(run.executor)
        assert "worker-prod" not in first and {"redis-prod", "web-prod"} <= set(first)
        assert second[-1] == "worker-prod" and "--remove-orphans" not in second
        assert "protected=worker-prod:updated" in run.result

    def test_busy_service_is_deferred(self, run):
        run(FakeExecutor({"worker busy": R(1, "")}), overrides=PROTECTED)
        assert run.code == 0
        assert run.result.split()[1] == "SUCCESS_PROTECTED_DEFERRED"
        assert "protected=worker-prod:deferred" in run.result
        assert "Busy protected services (worker-prod) stayed on the previous version" in run.message
        assert len(ups(run.executor)) == 1
        assert not run.executor.commands("worker pause")

    def test_no_answer_is_treated_as_busy(self, run):
        run(FakeExecutor({"worker busy": R(2, "timeout")}), overrides=PROTECTED)
        assert "did not answer its busy check" in run.out
        assert "protected=worker-prod:deferred" in run.result

    def test_busy_on_the_second_check_gives_the_work_back(self, run):
        run(FakeExecutor(first={"worker busy": [R(0, ""), R(1, "")]}), overrides=PROTECTED)
        assert run.executor.commands("worker resume")
        assert "protected=worker-prod:deferred" in run.result

    def test_quiesce_failure_resumes_and_defers(self, run):
        run(FakeExecutor({"worker pause": R(1, "")}), overrides=PROTECTED)
        assert run.executor.commands("worker resume")
        assert "protected=worker-prod:deferred" in run.result

    def test_stopped_service_is_left_alone(self, run):
        run(FakeExecutor({"{{.State.Running}}": R(0, "false\n")}), overrides=PROTECTED)
        assert run.code == 0
        assert run.result.split()[1] == "SUCCESS"
        assert "protected=worker-prod:stopped" in run.result
        assert "operator decision" in run.out
        assert all("worker-prod" not in " ".join(c[c.index("up") :]) for c in ups(run.executor))

    def test_absent_service_is_created(self, run):
        run(FakeExecutor({"com.docker.compose.service=worker-prod": R(0, "")}), overrides=PROTECTED)
        assert run.code == 0
        assert "worker-prod has no container yet: it is created." in run.out
        assert ups(run.executor)[1][-1] == "worker-prod"
        assert "protected=worker-prod:updated" in run.result
        assert not run.executor.commands("docker exec")

    def test_docker_error_listing_the_service_is_treated_as_busy(self, run):
        run(FakeExecutor({"com.docker.compose.service=worker-prod": R(1, "daemon error")}), overrides=PROTECTED)
        assert "protected=worker-prod:deferred" in run.result

    def test_failed_recreate_resumes_the_quiesced_service(self, run):
        run(FakeExecutor(first={"--remove-orphans": [R(1, "boom"), R(0, "")]}), overrides=PROTECTED)
        assert run.executor.commands("worker resume")

    def test_without_quiesce(self, run):
        overrides = {"protected_services": [{"service": "worker-prod", "busy_check": ["worker", "busy"]}]}
        run(overrides=overrides)
        assert len(run.executor.commands("docker exec")) == 1
        assert "protected=worker-prod:updated" in run.result

    def test_rollback_takes_an_idle_protected_service_back(self, run):
        health = [R(0, "unhealthy\n")] * 3 + [R(0, "healthy\n")]
        run(FakeExecutor(first={"{{.State.Health.Status}}": health}), overrides=PROTECTED)
        assert run.code == 4
        assert "protected=worker-prod:rolled_back" in run.result
        assert ups(run.executor)[-1][-1] == "worker-prod"

    def test_rollback_leaves_a_busy_protected_service_on_the_new_version(self, run):
        health = [R(0, "unhealthy\n")] * 3 + [R(0, "healthy\n")]
        busy = [R(0, ""), R(0, ""), R(1, "")]  # idle, idle after quiesce, busy at rollback
        run(FakeExecutor(first={"{{.State.Health.Status}}": health, "worker busy": busy}), overrides=PROTECTED)
        assert "stays on the new version" in run.out
        assert "protected=worker-prod:updated" in run.result


def with_script_in_commit(content: bytes, **responses):
    return FakeExecutor(
        {
            f"show {COMMIT}:deploy/deproi.py": R(0, content.decode("utf-8")),
            f"rev-parse {COMMIT}:deploy/deproi.py": R(0, deproi.git_blob_id(content) + "\n"),
            **responses,
        }
    )


NEW_SCRIPT = SCRIPT.replace(b'DEPROI_VERSION = "', b'DEPROI_VERSION = "9.')


class TestSelfUpdate:
    def test_up_to_date(self, run):
        run()
        assert f"Deploy script up to date ({deproi.fingerprint(SCRIPT)}, version {deproi.DEPROI_VERSION})." in run.out
        assert run.result.endswith("script=up_to_date")

    def test_new_version_is_installed_and_re_executed_with_the_lock(self, run):
        loaded = []
        run(
            with_script_in_commit(NEW_SCRIPT),
            environ={"PATH": "/usr/bin"},
            load=lambda path, executor: loaded.append(open(path, "rb").read()) or (True, ""),
        )
        assert loaded == [NEW_SCRIPT]
        assert open(run.installed, "rb").read() == NEW_SCRIPT
        assert oct(os.stat(run.installed).st_mode & 0o777) == "0o755"
        program, args, environ = run.executed[0]
        assert program == deproi.SERVER_PYTHON and args == [deproi.SERVER_PYTHON, run.installed]
        before, after = deproi.fingerprint(SCRIPT), deproi.fingerprint(NEW_SCRIPT)
        assert environ["DEPROI_SWAP"] == f"{before}:{after}"
        assert environ["DEPROI_LOCK_FD"] == "3" and environ["PATH"] == "/usr/bin"
        # The fake execve returns, which a real one never does: the old process stops without touching services.
        assert run.code == 3
        assert not run.executor.commands(" build")
        assert not os.path.exists(os.path.join(os.path.dirname(run.installed), ".deproi-myapp-prod.new"))

    def test_version_that_does_not_load_is_not_installed(self, run):
        run(with_script_in_commit(NEW_SCRIPT), load=lambda path, executor: (False, "SyntaxError: boom"))
        assert run.code == 3
        assert "does not load" in run.message
        assert open(run.installed, "rb").read() == SCRIPT
        assert run.result.endswith("script=refused")
        assert not run.executed

    def test_unreadable_script_in_the_commit(self, run):
        run(FakeExecutor({f"rev-parse {COMMIT}:deploy/deproi.py": R(0, "0" * 40 + "\n")}))
        assert run.code == 3
        assert "Could not read the deploy script" in run.message
        assert run.result.endswith("script=refused")

    def test_re_executed_process_records_the_swap(self, run):
        before, after = "1" * 12, deproi.fingerprint(SCRIPT)
        run(environ={"DEPROI_SWAP": f"{before}:{after}"})
        assert run.code == 0
        assert run.result.endswith(f"script=updated:{before}:{after}")
        assert run.message.endswith(" Deploy script updated.")

    def test_branch_moved_between_the_swap_and_now(self, run):
        run(with_script_in_commit(NEW_SCRIPT), environ={"DEPROI_SWAP": f"{'1' * 12}:{'2' * 12}"})
        assert run.code == 0
        assert run.result.endswith("script=pending")
        assert not run.executed

    def test_already_installed_by_another_deploy(self, run):
        with open(run.installed, "wb") as handle:
            handle.write(NEW_SCRIPT)
        run(with_script_in_commit(NEW_SCRIPT), load=lambda *a: pytest.fail("must not load again"))
        assert len(run.executed) == 1

    def test_custom_script_path(self, run):
        run(
            FakeExecutor(
                {
                    f"show {COMMIT}:ops/deproi.py": R(0, SCRIPT.decode()),
                    f"rev-parse {COMMIT}:ops/deproi.py": R(0, deproi.git_blob_id(SCRIPT) + "\n"),
                }
            ),
            overrides={"script_path": "ops/deproi.py"},
        )
        assert run.code == 0


def loader_accepts(tmp_path, content: str) -> tuple:
    path = tmp_path / "candidate.py"
    path.write_text(content)
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", deproi.LOADER, str(path)], capture_output=True, text=True, check=False
    )
    return result.returncode == 0, result.stderr


class TestLoader:
    def test_accepts_this_deproi(self, tmp_path):
        assert loader_accepts(tmp_path, (ROOT / "deproi.py").read_text()) == (True, "")

    def test_refuses_a_version_without_the_marker(self, tmp_path):
        ok, why = loader_accepts(tmp_path, "def main(): pass\n")
        assert not ok and "SELF_UPDATING" in why

    def test_refuses_a_version_without_main(self, tmp_path):
        ok, why = loader_accepts(tmp_path, "SELF_UPDATING = True\n")
        assert not ok and "no main" in why

    def test_refuses_a_version_that_exits_while_loading(self, tmp_path):
        ok, why = loader_accepts(tmp_path, "import sys\nsys.exit(0)\n")
        assert not ok and "exits while loading" in why

    def test_refuses_a_syntax_error(self, tmp_path):
        assert loader_accepts(tmp_path, "def main(:\n")[0] is False


class TestLock:
    def test_acquire_and_timeout(self, tmp_path):
        path = str(tmp_path / "x.lock")
        first = deproi.acquire_lock(path, 0)
        assert first is not None
        from conftest import Clock

        clock = Clock()
        assert deproi.acquire_lock(path, 10, clock, clock.sleep) is None
        assert clock.sleeps == [5, 5]
        os.close(first)

    def test_inherited_lock_is_adopted_only_for_the_same_file(self, tmp_path):
        path, other = str(tmp_path / "x.lock"), str(tmp_path / "y.lock")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        open(other, "w").close()
        assert deproi.adopt_lock({"DEPROI_LOCK_FD": str(descriptor)}, path) == descriptor
        assert deproi.adopt_lock({"DEPROI_LOCK_FD": str(descriptor)}, other) is None
        assert deproi.adopt_lock({"DEPROI_LOCK_FD": "not-a-number"}, path) is None
        assert deproi.adopt_lock({}, path) is None
        os.close(descriptor)

    def test_swap_variable_format(self):
        assert deproi.read_swap({"DEPROI_SWAP": f"{'a' * 12}:{'b' * 12}"}) == ("a" * 12, "b" * 12)
        assert deproi.read_swap({"DEPROI_SWAP": "; rm -rf /"}) is None


def test_previous_constant_matches_test_data():
    assert len(PREVIOUS) == 12
