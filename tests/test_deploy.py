"""The deploy flow, end to end, with a fake executor."""

from __future__ import annotations

import pytest
from conftest import COMMIT, GB, PREVIOUS, WEB_ID, FakeExecutor, definition

import deproi

R = deproi.Result


def failing_health():
    return {"{{.State.Health.Status}}": R(0, "unhealthy\n")}


class TestHappyPath:
    def test_success(self, run):
        run()
        assert run.code == 0
        assert run.result == (
            f"result: SUCCESS commit={COMMIT} previous={PREVIOUS} duration=0s protected=- step=cleanup "
            "script=up_to_date"
        )
        assert run.message == f"myapp-prod published: commit {COMMIT} is live at https://app.example.com (1 min)."
        assert "::error::" not in run.out

    def test_banner_and_steps_are_grouped(self, run):
        run()
        assert run.out.splitlines()[0] == f"Deproi {deproi.DEPROI_VERSION} — myapp-prod"
        for title in (
            "Lock",
            "Disk space",
            "Update the code",
            "Deploy script",
            "Compose definition",
            f"Build the image myapp:{COMMIT}",
            "Recreate the services",
            "Clean up old images",
        ):
            assert f"::group::{title}" in run.out
        assert run.out.count("::group::") == run.out.count("::endgroup::")

    def test_git_runs_as_the_checkout_owner(self, run):
        run()
        fetch = run.executor.commands("fetch")[0]
        assert fetch == [
            "runuser",
            "-u",
            "deployer",
            "--",
            "env",
            "HOME=/home/deployer",
            "git",
            "-C",
            "/srv/myapp",
            "fetch",
            "origin",
            "main",
        ]

    def test_git_sequence_never_discards_work(self, run):
        run()
        git = [c[9] for c in run.executor.commands("git -C")]
        assert git[:6] == ["fetch", "rev-parse", "status", "show", "merge-base", "merge"]
        assert not {"reset", "clean", "stash", "checkout"} & set(git)

    def test_compose_command_is_fenced_to_the_project(self, run):
        run()
        build = run.executor.commands("docker compose")[0]
        assert build[build.index("compose") + 1 : build.index("compose") + 3] == ["--project-name", "myapp-prod"]
        text = " ".join(build)
        assert (
            "-f compose.yaml --env-file deploy/prod.compose.env --env-file /etc/deproi/myapp-prod.secrets.env" in text
        )
        assert "--profile prod" in text

    def test_build_is_low_priority_with_the_commit_tag(self, run):
        run()
        build = run.executor.call(
            "compose --project-name myapp-prod -f compose.yaml --env-file deploy/prod.compose.env "
            "--env-file /etc/deproi/myapp-prod.secrets.env --profile prod build"
        )
        assert build.command[:5] == ["nice", "-n", "10", "ionice", "-c3"]
        assert build.env == {"DEPROI_TAG": COMMIT}
        assert build.cwd == "/srv/myapp"

    def test_build_options(self, run):
        run(overrides={"build": {"low_priority": False, "pull": True}})
        build = run.executor.commands(" build")[0]
        assert build[0] == "docker" and build[-1] == "--pull"

    def test_custom_tag_variables(self, run):
        run(overrides={"compose": {"tag_variables": ["APP_TAG", "APP_RELEASE"]}})
        assert run.executor.call(" build").env == {"APP_TAG": COMMIT, "APP_RELEASE": COMMIT}

    def test_whole_profile_is_recreated_without_a_list(self, run):
        run()
        up = run.executor.commands(" up ")
        assert len(up) == 1
        assert up[0][-3:] == ["up", "-d", "--remove-orphans"]
        assert run.executor.call(" up ").env == {"DEPROI_TAG": COMMIT}

    def test_removed_containers_are_reported(self, run):
        run(FakeExecutor({" up ": R(0, " Container myapp-prod-old-1  Removed\n")}))
        assert "Removed services (containers): myapp-prod-old-1" in run.out

    def test_health_is_read_from_the_web_containers(self, run):
        run()
        assert f"{{{{if .State.Health}}}}{{{{.State.Health.Status}}}}{{{{else}}}}none{{{{end}}}} {WEB_ID}" in " ".join(
            run.executor.texts("State.Health")
        )
        assert "health of web-prod: healthy" in run.out

    def test_cleanup_removes_only_old_deproi_tags(self, run):
        old, in_use = "222222222222", "333333333333"
        run(
            FakeExecutor(
                {
                    "image ls": R(0, f"{COMMIT}\n{PREVIOUS}\n{old}\n{in_use}\nlatest\nabc1234\n"),
                    "--format {{.Image}}": R(0, f"myapp:{COMMIT}\nmyapp:{in_use}\n"),
                }
            )
        )
        removed = [c[-1] for c in run.executor.commands("image rm")]
        assert removed == [f"myapp:{old}"]
        assert run.executor.commands("builder prune")

    def test_cleanup_failure_does_not_fail_the_deploy(self, run):
        run(FakeExecutor({"image ls": R(1, "boom")}))
        assert run.code == 0
        assert "cleanup is left for the next deploy" in run.out

    def test_post_deploy_is_scheduled_only_when_live(self, run):
        run()
        assert len(run.background) == 1

    def test_syslog_records_start_and_result(self, run):
        run(environ={"SUDO_USER": "deploy", "SSH_ORIGINAL_COMMAND": "rm -rf /"})
        logs = [c[-1] for c in run.executor.commands("logger")]
        assert logs[0].startswith(f"start version={deproi.DEPROI_VERSION} origin=deploy")
        assert "ssh_original_command='rm -rf /'" in logs[0]
        assert logs[-1] == run.result
        assert all(c[0] == "logger" for c in run.executor.commands("rm -rf"))

    def test_portuguese_messages(self, run):
        run(overrides={"language": "pt-BR"})
        assert run.message.startswith(f"myapp-prod publicado: commit {COMMIT} no ar em https://app.example.com")
        assert "::group::Atualizar o código" in run.out
        assert run.result.startswith("result: SUCCESS ")

    def test_without_url(self, run):
        run(overrides={"url": None})
        assert run.message == f"myapp-prod published: commit {COMMIT} is live (1 min)."

    def test_without_env_file_there_is_no_project_check(self, run):
        run(overrides={"compose": {"env_file": None}})
        assert run.code == 0
        assert not run.executor.commands("show origin/main")
        assert "--env-file deploy/prod.compose.env" not in " ".join(run.executor.texts("compose"))


class TestRefusedEarly:
    def test_arguments_are_refused(self, run):
        run(argv=["--target", "prod"])
        assert run.code == 2
        assert run.message == "This command accepts no arguments."
        assert not run.executor.commands("git")

    def test_must_be_root(self, run):
        run(euid=1000)
        assert run.code == 2
        assert "sudo " in run.message

    def test_invalid_config(self, run):
        run(config_error="unknown key colour")
        assert run.code == 2
        assert (
            run.message
            == "Invalid configuration in /etc/deproi/myapp-prod.json: unknown key colour — nothing was done."
        )
        assert run.result.startswith("result: REFUSED commit=- ")
        assert not run.background

    def test_lock_held_too_long(self, run):
        run(lock=None)
        assert run.code == 2
        assert "Another deploy has been running for more than 30 minutes" in run.message
        assert not run.executor.commands("git")

    def test_low_disk(self, run):
        run(free=2 * GB)
        assert run.code == 3
        assert "only 2.0 GB free" in run.message
        assert not run.executor.commands("git")


class TestCheckout:
    def test_fetch_failure(self, run):
        run(FakeExecutor({"fetch": R(128, "fatal: could not read")}))
        assert run.code == 3
        assert "Could not fetch main from origin" in run.message

    def test_wrong_branch(self, run):
        run(FakeExecutor({"rev-parse --abbrev-ref HEAD": R(0, "hotfix\n")}))
        assert run.code == 2
        assert "on branch hotfix, not main" in run.message

    def test_dirty_checkout_names_the_files(self, run):
        status = " M a.py\n M b.py\n M c.py\n M d.py\n M e.py\n"
        run(FakeExecutor({"status --porcelain": R(0, status)}))
        assert run.code == 2
        assert "local changes in a.py, b.py, c.py (and 2 more)" in run.message
        assert not run.executor.commands("merge --ff-only")

    def test_env_file_must_exist_in_the_branch(self, run):
        run(FakeExecutor({"show origin/main:deploy/prod.compose.env": R(128, "fatal: path")}))
        assert run.code == 2
        assert "deploy/prod.compose.env was not found in main" in run.message
        assert not run.executor.commands("merge --ff-only")

    def test_env_file_must_point_to_the_project(self, run):
        run(FakeExecutor({"show origin/main:deploy/prod.compose.env": R(0, "COMPOSE_PROJECT_NAME=myapp-test\n")}))
        assert run.code == 2
        assert "points to project myapp-test, not myapp-prod" in run.message
        assert not run.executor.commands("merge --ff-only")

    def test_diverged_branch(self, run):
        run(FakeExecutor({"merge-base --is-ancestor": R(1, "")}))
        assert run.code == 2
        assert "has commits that are not on origin" in run.message

    def test_fast_forward_failure(self, run):
        run(FakeExecutor({"merge --ff-only": R(1, "error: untracked working tree files would be overwritten")}))
        assert run.code == 2
        assert "untracked file" in run.message

    def test_unexpected_commit_format(self, run):
        run(FakeExecutor({"rev-parse --short=12 HEAD": R(0, "not-a-sha\n")}))
        assert run.code == 3


class TestDefinition:
    def test_compose_config_failure(self, run):
        run(FakeExecutor({"config --format json": R(1, "service x: invalid\n")}))
        assert run.code == 3
        assert "Could not read the Compose definition" in run.message
        assert "service x: invalid" in run.out
        assert not run.executor.commands(" build")

    def test_services_without_the_suffix_are_refused(self, run):
        run(FakeExecutor({"config --format json": R(0, definition(extra={"postgres": {"image": "postgres"}}))}))
        assert run.code == 2
        assert "without the suffix -prod (postgres)" in run.message
        assert not run.executor.commands(" build")

    def test_web_service_must_exist(self, run):
        run(overrides={"compose": {"web_service": "api-prod"}})
        assert run.code == 2
        assert "has no service api-prod" in run.message

    def test_built_services_must_use_the_commit_tag(self, run):
        bad = definition().replace(f'"image": "myapp:{COMMIT}", "build"', '"image": "myapp:latest", "build"')
        run(FakeExecutor({"config --format json": R(0, bad)}))
        assert run.code == 2
        assert f"uses image myapp:latest, but Deproi expects myapp:{COMMIT}" in run.message
        assert "image: myapp:${DEPROI_TAG}" in run.message

    def test_empty_definition(self, run):
        run(FakeExecutor({"config --format json": R(0, '{"services": {}}')}))
        assert run.code == 2

    def test_secrets_in_the_definition_are_never_printed(self, run):
        secret = definition(extra={"db-prod": {"image": "postgres", "environment": {"PASSWORD": "hunter2"}}})
        run(FakeExecutor({"config --format json": R(0, secret)}))
        assert "hunter2" not in run.out


class TestBuildAndHealthcheck:
    def test_build_failure(self, run):
        run(FakeExecutor({" build": R(1, "")}))
        assert run.code == 3
        assert f"The image of commit {COMMIT} did not build" in run.message
        assert not run.executor.commands(" up ")

    def test_healthcheck_is_required(self, run):
        run(
            FakeExecutor(
                {
                    "config --format json": R(0, definition(web_health=False)),
                    "image inspect": R(0, "null\n"),
                }
            )
        )
        assert run.code == 2
        assert "has no health check" in run.message
        assert not run.executor.commands(" up ")

    def test_healthcheck_from_the_dockerfile(self, run):
        run(
            FakeExecutor(
                {
                    "config --format json": R(0, definition(web_health=False)),
                    "image inspect": R(0, '{"Test": ["CMD-SHELL", "curl -f localhost"]}\n'),
                }
            )
        )
        assert run.code == 0
        assert "Health check found (Dockerfile HEALTHCHECK)" in run.out

    def test_disabled_healthcheck_is_refused(self, run):
        disabled = definition(extra={"web-prod": {"image": f"myapp:{COMMIT}", "healthcheck": {"disable": True}}})
        run(FakeExecutor({"config --format json": R(0, disabled)}))
        assert run.code == 2


HOOKS = {
    "pre_migrate": [{"name": "check", "command": ["python", "manage.py", "check", "--deploy"]}],
    "migrate": [{"name": "migrate", "command": ["python", "manage.py", "migrate"], "env": {"COLLECT": "0"}}],
    "post_migrate": [{"name": "flags", "command": ["python", "manage.py", "sync_flags"]}],
}


class TestHooks:
    def test_hooks_run_in_order_on_the_new_image(self, run):
        run(overrides={"hooks": HOOKS})
        hooks = run.executor.commands(" run --rm")
        assert [h[-1] for h in hooks] == ["--deploy", "migrate", "sync_flags"]
        migrate = hooks[1]
        assert migrate[migrate.index("run") :] == [
            "run",
            "--rm",
            "--no-deps",
            "-e",
            "COLLECT=0",
            "web-prod",
            "python",
            "manage.py",
            "migrate",
        ]
        assert run.executor.call("manage.py migrate").env == {"DEPROI_TAG": COMMIT}
        texts = " ".join(c[-1] if c[0] == "logger" else " ".join(c) for c in run.executor.commands())
        assert texts.index("manage.py migrate") < texts.index(" up -d")

    def test_no_hooks(self, run):
        run()
        assert run.out.splitlines().count("No hooks configured.") == 3

    def test_pre_migrate_failure_stops_before_migrations(self, run):
        run(FakeExecutor({"check --deploy": R(1, "")}), overrides={"hooks": HOOKS})
        assert run.code == 3
        assert (
            run.message == "Hook check (pre_migrate) failed (exit 1) — no service was recreated. See the error above."
        )
        assert not run.executor.commands("manage.py migrate")

    def test_refusing_hook(self, run):
        hooks = {"pre_migrate": [{"name": "runbook", "command": ["guard"], "on_failure": "refuse"}]}
        run(FakeExecutor({"guard": R(1, "")}), overrides={"hooks": hooks})
        assert run.code == 2
        assert "refused the deploy" in run.message

    def test_migration_failure(self, run):
        run(FakeExecutor({"manage.py migrate": R(1, "")}), overrides={"hooks": HOOKS})
        assert run.code == 3
        assert "Migrations applied before the failure stay applied" in run.message
        assert not run.executor.commands(" up ")

    def test_post_migrate_failure_only_warns(self, run):
        run(FakeExecutor({"sync_flags": R(1, "")}), overrides={"hooks": HOOKS})
        assert run.code == 0
        assert "Warning: hook flags failed (exit 1) — the deploy continues." in run.out

    def test_migrate_hooks_share_one_deadline(self, run):
        clock = None
        hooks = {"migrate": [{"name": "first", "command": ["one"]}, {"name": "second", "command": ["two"]}]}

        class Slow(FakeExecutor):
            def run(self, command, **kwargs):
                if command[-1] == "one":
                    clock.now += 3000
                return super().run(command, **kwargs)

        from conftest import Clock

        clock = Clock()
        run(Slow(), overrides={"hooks": hooks}, clock=clock)
        assert run.code == 3
        assert "Migrations went past 40 minutes and stopped before second" in run.message
        assert run.executor.call(" one").timeout == 2400

    def test_hook_timeout(self, run):
        hooks = {"post_migrate": [{"name": "slow", "command": ["slow"], "timeout": 30}]}
        run(overrides={"hooks": hooks})
        assert run.executor.call(" slow").timeout == 30


class TestRollback:
    def test_unhealthy_version_rolls_back_with_the_previous_definition(self, run):
        run(FakeExecutor(first={"{{.State.Health.Status}}": [R(0, "unhealthy\n")] * 49 + [R(0, "healthy\n")]}))
        assert run.code == 4
        assert run.message == (
            f"Version {COMMIT} did not become healthy — the environment went back to {PREVIOUS}. "
            "Applied migrations were not undone."
        )
        ups = run.executor.calls
        ups = [c for c in ups if " up " in " ".join(c.command)]
        assert len(ups) == 2
        back = ups[1]
        assert back.env == {"DEPROI_TAG": PREVIOUS}
        text = " ".join(back.command)
        assert "--project-directory /srv/myapp" in text
        assert "/0-compose.yaml" in text and text.count("--env-file") == 2
        assert "Using the Compose definition of 111111111111." in run.out
        assert not run.background
        assert run.result.split()[1] == "FAILED_ROLLED_BACK"

    def test_health_waits_until_the_deadline(self, run):
        run(FakeExecutor(failing_health()))
        assert run.clock.sleeps.count(5) >= 48

    def test_rollback_that_also_fails(self, run):
        run(FakeExecutor(failing_health()))
        assert run.code == 5
        assert "going back to 111111111111 did not work either" in run.message

    def test_first_deploy_has_nothing_to_roll_back_to(self, run):
        run(FakeExecutor({**failing_health(), "{{.Config.Image}}": R(1, "No such object")}))
        assert run.code == 3
        assert "there is no previous version to go back to" in run.message

    def test_image_from_another_repository_is_not_a_previous_version(self, run):
        run(FakeExecutor({**failing_health(), "{{.Config.Image}}": R(0, "other:111111111111\n")}))
        assert "there is no previous version" in run.message

    def test_failed_recreate_rolls_back(self, run):
        run(FakeExecutor(first={" up ": [R(1, "port is already allocated"), R(0, "")]}))
        assert run.code == 4

    def test_previous_definition_missing_uses_the_current_one(self, run):
        run(
            FakeExecutor(
                first={
                    f"show {PREVIOUS}:compose.yaml": R(128, "fatal: invalid object"),
                    "{{.State.Health.Status}}": [R(0, "unhealthy\n")] * 49 + [R(0, "healthy\n")],
                }
            )
        )
        assert run.code == 4
        assert "the rollback uses the current one" in run.out

    def test_previous_definition_of_another_project_is_not_used(self, run):
        run(
            FakeExecutor(
                first={
                    f"show {PREVIOUS}:deploy/prod.compose.env": R(0, "COMPOSE_PROJECT_NAME=other\n"),
                    "{{.State.Health.Status}}": [R(0, "unhealthy\n")] * 49 + [R(0, "healthy\n")],
                }
            )
        )
        assert "the rollback uses the current one" in run.out


class TestRepublish:
    def test_same_commit_is_force_recreated(self, run):
        run(FakeExecutor({"{{.Config.Image}}": R(0, f"myapp:{COMMIT}\n")}))
        assert run.code == 0
        assert "--force-recreate" in run.executor.commands(" up ")[0]
        assert "Same commit already live" in run.out

    def test_same_commit_unhealthy_cannot_roll_back(self, run):
        run(FakeExecutor({**failing_health(), "{{.Config.Image}}": R(0, f"myapp:{COMMIT}\n")}))
        assert run.code == 5
        assert "it is the same one that was already live" in run.message


class TestUnexpectedErrors:
    def test_before_touching_services(self, run, monkeypatch):
        monkeypatch.setattr(deproi, "check_disk", lambda cfg, free: 1 / 0)
        run()
        assert run.code == 3
        assert "Unexpected error at step disk (ZeroDivisionError" in run.message
        assert run.result.startswith("result: FAILED_NO_CHANGE")

    def test_after_touching_services(self, run, monkeypatch):
        monkeypatch.setattr(deproi, "wait_healthy", lambda *a: 1 / 0)
        run()
        assert run.code == 5
        assert run.result.startswith("result: FAILED_ROLLBACK")


class TestOutput:
    def test_write_survives_a_broken_pipe(self, monkeypatch):
        def broken(*args, **kwargs):
            raise BrokenPipeError

        dup2 = []
        monkeypatch.setattr("builtins.print", broken)
        monkeypatch.setattr(deproi.os, "dup2", lambda a, b: dup2.append(b))
        deproi.write("one")
        deproi.write("two")
        assert deproi._broken_output is True
        assert len(dup2) == 1

    def test_result_line_lists_protected_services(self):
        deploy = deproi.Deploy(
            commit=COMMIT,
            situation=deproi.Situation.SUCCESS_PROTECTED_DEFERRED,
            protected={"worker-prod": "deferred", "beat-prod": "updated"},
            step="cleanup",
        )
        line = deproi.result_line(deploy, 61.7)
        assert line == (
            f"result: SUCCESS_PROTECTED_DEFERRED commit={COMMIT} previous=- duration=61s "
            "protected=beat-prod:updated,worker-prod:deferred step=cleanup script=not_checked"
        )

    @pytest.mark.parametrize(
        ("situation", "code"),
        [
            ("SUCCESS", 0),
            ("SUCCESS_PROTECTED_DEFERRED", 0),
            ("REFUSED", 2),
            ("FAILED_NO_CHANGE", 3),
            ("FAILED_ROLLED_BACK", 4),
            ("FAILED_ROLLBACK", 5),
        ],
    )
    def test_exit_codes(self, situation, code):
        assert deproi.Situation[situation].code == code


class TestRealExecutor:
    def test_capture(self):
        result = deproi.RealExecutor().run(["python3", "-c", "print('hi')"], capture=True)
        assert result == deproi.Result(0, "hi\n")

    def test_streams_without_capture(self, capsys):
        result = deproi.RealExecutor().run(["python3", "-c", "import sys; print('out'); print('err', file=sys.stderr)"])
        assert result.code == 0
        # stderr is merged into the same stream (order depends on the child's buffering).
        assert sorted(capsys.readouterr().out.splitlines()) == ["err", "out"]

    def test_echo_and_capture(self, capsys):
        result = deproi.RealExecutor().run(["python3", "-c", "print('both')"], capture=True, echo=True)
        assert result.output == "both\n"
        assert capsys.readouterr().out == "both\n"

    def test_timeout(self):
        result = deproi.RealExecutor().run(["python3", "-c", "import time; time.sleep(5)"], timeout=0.3)
        assert result.code == 124

    def test_missing_program(self):
        assert deproi.RealExecutor().run(["/nonexistent/program"]).code == 127

    def test_env_is_added_to_the_process_environment(self):
        result = deproi.RealExecutor().run(
            ["python3", "-c", "import os; print(os.environ['DEPROI_X'], 'PATH' in os.environ)"],
            env={"DEPROI_X": "1"},
            capture=True,
        )
        assert result.output == "1 True\n"


class TestEntry:
    def test_unknown_path_is_refused(self, capsys):
        assert deproi.entry(["/tmp/deproi.py"]) == 2
        assert "result: REFUSED" in capsys.readouterr().out

    def test_name_must_be_valid(self, capsys):
        assert deproi.entry(["/usr/local/sbin/deproi-Bad_Name"]) == 2

    def test_installed_path_selects_the_name(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            deproi, "main", lambda argv, name, installed: seen.update(argv=argv, name=name, installed=installed) or 0
        )
        assert deproi.entry(["/usr/local/sbin/deproi-myapp-prod", "x"]) == 0
        assert seen == {"argv": ["x"], "name": "myapp-prod", "installed": "/usr/local/sbin/deproi-myapp-prod"}
