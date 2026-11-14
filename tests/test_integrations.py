"""Better Stack, Cloudflare, webhook, post-deploy and the bilingual messages."""

from __future__ import annotations

import io
import json
import re
import string
import urllib.error
from types import SimpleNamespace

import pytest
from conftest import COMMIT, PREVIOUS, FakeExecutor, make_config, root_stat

import deproi

R = deproi.Result
TOKEN = "tok-secret-123"


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Answers by URL fragment; records requests."""

    def __init__(self, answers=None):
        self.requests = []
        self.answers = answers or {}

    def __call__(self, request, timeout=None):
        assert timeout == deproi.HTTP_TIMEOUT
        body = json.loads(request.data) if request.data else None
        self.requests.append(
            SimpleNamespace(
                method=request.get_method(), url=request.full_url, body=body, headers=dict(request.header_items())
            )
        )
        for fragment, answer in self.answers.items():
            if fragment in request.full_url:
                if isinstance(answer, BaseException):
                    raise answer
                if isinstance(answer, list):
                    answer = answer.pop(0) if len(answer) > 1 else answer[0]
                return Response(json.dumps(answer).encode())
        return Response(b"{}")


def http_error(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


def credentials(tmp_path, name, **values):
    path = tmp_path / name
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    path.chmod(0o600)
    return str(path)


def integrations_with(opener):
    return lambda c, e: deproi.Integrations(c, e, opener=opener, stat_fn=root_stat)


class TestCredentials:
    def test_reads_env_format(self, tmp_path):
        path = credentials(tmp_path, "c.env", A="1")
        assert deproi.read_credentials(path, ("A",), root_stat) == ({"A": "1"}, None)

    def test_missing_keys(self, tmp_path):
        path = credentials(tmp_path, "c.env", A="1")
        _, problem = deproi.read_credentials(path, ("A", "B"), root_stat)
        assert "missing B" in problem

    def test_insecure_file(self, tmp_path):
        path = credentials(tmp_path, "c.env", A="1")
        insecure = lambda p: SimpleNamespace(st_uid=0, st_mode=0o100644)  # noqa: E731
        assert "owned by root" in deproi.read_credentials(path, ("A",), insecure)[1]

    def test_env_values_parsing(self):
        assert deproi.env_values("# c\nexport A='1'\nB=\"two\"\n\nbad\nC = 3\n") == {"A": "1", "B": "two", "C": "3"}


class TestCloudflare:
    def overrides(self, path):
        return {"integrations": {"cloudflare": {"credentials_file": path, "zone_id": "f" * 32}}}

    def test_purges_the_hosts_after_success(self, run, tmp_path):
        opener = FakeOpener({"purge_cache": {"success": True}})
        path = credentials(tmp_path, "cf.env", CLOUDFLARE_API_TOKEN=TOKEN)
        run(overrides=self.overrides(path), integrations=integrations_with(opener))
        assert run.line("cloudflare: ") == "cloudflare: cache purged (app.example.com)"
        request = opener.requests[0]
        assert request.url == f"https://api.cloudflare.com/client/v4/zones/{'f' * 32}/purge_cache"
        assert request.body == {"hosts": ["app.example.com"]}
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"

    def test_failure_is_a_warning_and_never_leaks_the_token(self, run, tmp_path):
        opener = FakeOpener({"purge_cache": {"success": False, "errors": [{"code": 10000, "message": TOKEN}]}})
        path = credentials(tmp_path, "cf.env", CLOUDFLARE_API_TOKEN=TOKEN)
        run(overrides=self.overrides(path), integrations=integrations_with(opener))
        assert run.code == 0
        assert "purge failed — success:false (10000: [secret])" in run.line("cloudflare: ")
        assert TOKEN not in run.out

    def test_http_error(self, run, tmp_path):
        path = credentials(tmp_path, "cf.env", CLOUDFLARE_API_TOKEN=TOKEN)
        run(overrides=self.overrides(path), integrations=integrations_with(FakeOpener({"purge": http_error(403)})))
        assert "HTTP 403" in run.line("cloudflare: ")

    def test_no_purge_when_the_version_is_not_live(self, run, tmp_path):
        opener = FakeOpener()
        path = credentials(tmp_path, "cf.env", CLOUDFLARE_API_TOKEN=TOKEN)
        run(FakeExecutor({" build": R(1, "")}), overrides=self.overrides(path), integrations=integrations_with(opener))
        assert run.line("cloudflare: ") == "cloudflare: no purge: the new version is not live"
        assert not opener.requests

    def test_off_without_configuration(self, run):
        run()
        assert run.line("cloudflare: ") == "cloudflare: purge off"

    def test_no_summary_lines_before_the_config_is_loaded(self, run):
        run(config_error="bad")
        assert "cloudflare: " not in run.out


class TestWebhook:
    def overrides(self, path, **extra):
        return {"integrations": {"webhook": {"url_file": path, **extra}}}

    def test_json_payload(self, run, tmp_path):
        opener = FakeOpener()
        path = credentials(tmp_path, "wh.env", WEBHOOK_URL="https://hooks.example.com/abc")
        run(overrides=self.overrides(path), integrations=integrations_with(opener))
        assert run.line("webhook: ") == "webhook: sent"
        body = opener.requests[0].body
        assert body["situation"] == "SUCCESS" and body["commit"] == COMMIT and body["previous"] == PREVIOUS
        assert body["deproi_version"] == deproi.DEPROI_VERSION

    @pytest.mark.parametrize(("fmt", "key"), [("slack", "text"), ("discord", "content")])
    def test_chat_formats(self, run, tmp_path, fmt, key):
        opener = FakeOpener()
        path = credentials(tmp_path, "wh.env", WEBHOOK_URL="https://hooks.example.com/abc")
        run(overrides=self.overrides(path, format=fmt), integrations=integrations_with(opener))
        assert opener.requests[0].body[key].startswith("✅ myapp-prod: myapp-prod published")

    def test_only_selected_events(self, run, tmp_path):
        opener = FakeOpener()
        path = credentials(tmp_path, "wh.env", WEBHOOK_URL="https://hooks.example.com/abc")
        run(overrides=self.overrides(path, events=["failure"]), integrations=integrations_with(opener))
        assert run.line("webhook: ") == "webhook: not sent for SUCCESS"
        assert not opener.requests

    def test_failure_does_not_change_the_outcome_nor_leak_the_url(self, run, tmp_path):
        url = "https://hooks.example.com/secret-path"
        opener = FakeOpener({"hooks.example.com": urllib.error.URLError(f"cannot reach {url}")})
        path = credentials(tmp_path, "wh.env", WEBHOOK_URL=url)
        run(overrides=self.overrides(path), integrations=integrations_with(opener))
        assert run.code == 0
        assert run.line("webhook: ").startswith("webhook: failed")
        assert "secret-path" not in run.out

    def test_only_https(self, run, tmp_path):
        path = credentials(tmp_path, "wh.env", WEBHOOK_URL="http://hooks.example.com/abc")
        run(overrides=self.overrides(path), integrations=integrations_with(FakeOpener()))
        assert "only https" in run.line("webhook: ")


class FakeBetterStack:
    def __init__(self, monitors=None, fail_patch=False):
        self.monitors = monitors or {"1": {"confirmation_period": 0}, "2": {"confirmation_period": 3}}
        self.patches = []
        self.fail_patch = fail_patch
        self.secrets = (TOKEN,)
        self.uptime_token = TOKEN
        self.errors_token = TOKEN
        self.registered = []
        self.existing = []

    def monitor(self, monitor_id):
        if monitor_id not in self.monitors:
            raise deproi.IntegrationError(f"GET monitor {monitor_id}: HTTP 404")
        return self.monitors[monitor_id]

    def update_monitor(self, monitor_id, fields):
        if self.fail_patch:
            raise deproi.IntegrationError(f"PATCH {TOKEN}: HTTP 500")
        self.patches.append((monitor_id, fields))

    def releases(self, version):
        return self.existing

    def register_release(self, version):
        self.registered.append(version)


def bs_settings(**kwargs):
    defaults = {
        "credentials_file": "/etc/x",
        "monitors": ("1", "2", "3"),
        "grace_period": 1200,
        "errors_application": "9",
        "errors_environment": "production",
    }
    return deproi.BetterStackSettings(**{**defaults, **kwargs})


class TestMonitors:
    def test_widen_saves_state_first_and_skips_paused(self, tmp_path):
        client = FakeBetterStack(
            {"1": {"confirmation_period": 0}, "2": {"paused": True}, "3": {"confirmation_period": 1800}}
        )
        state = str(tmp_path / "s" / "monitors.json")
        protection = deproi.widen_monitors(client, bs_settings(), state, COMMIT)
        assert protection.widened == ["1"] and protection.paused == ["2"]
        assert client.patches == [("1", {"confirmation_period": 1200})]
        assert deproi.read_json(state)["monitors"] == {"1": {"confirmation_period": 0}}

    def test_restore_puts_values_back_and_removes_the_state(self, tmp_path):
        client = FakeBetterStack()
        state = str(tmp_path / "monitors.json")
        deproi.write_json(state, {"monitors": {"1": {"confirmation_period": 0}}})
        restoration = deproi.restore_monitors(client, state)
        assert restoration.restored == ["1"] and client.patches == [("1", {"confirmation_period": 0})]
        assert deproi.read_json(state) is None

    def test_restore_failure_keeps_the_leftover_and_redacts(self, tmp_path):
        client = FakeBetterStack(fail_patch=True)
        state = str(tmp_path / "monitors.json")
        deproi.write_json(state, {"monitors": {"1": {"confirmation_period": 0}}})
        restoration = deproi.restore_monitors(client, state)
        assert restoration.failures == ["1: PATCH [secret]: HTTP 500"]
        assert deproi.read_json(state)["monitors"] == {"1": {"confirmation_period": 0}}

    def test_leftover_from_a_dead_deploy_is_not_overwritten(self, tmp_path):
        client = FakeBetterStack({"1": {"confirmation_period": 1200}})
        state = str(tmp_path / "monitors.json")
        deproi.write_json(state, {"monitors": {"1": {"confirmation_period": 30}}})
        deproi.widen_monitors(client, bs_settings(monitors=("1",)), state, COMMIT)
        assert deproi.read_json(state)["monitors"]["1"] == {"confirmation_period": 30}

    def test_release_is_registered_once(self):
        client = FakeBetterStack()
        assert deproi.register_release(client, bs_settings(), COMMIT) == {"ok": True, "existed": False}
        client.existing = [{"attributes": {"version": COMMIT, "environments": ["production"]}}]
        assert deproi.register_release(client, bs_settings(), COMMIT) == {"ok": True, "existed": True}
        assert client.registered == [COMMIT]


class TestBetterStackClient:
    def client(self, opener):
        return deproi.BetterStackClient(bs_settings(), TOKEN, "err-token", opener)

    def test_circuit_breaker_after_a_connection_failure(self):
        opener = FakeOpener({"monitors": urllib.error.URLError("down")})
        client = self.client(opener)
        with pytest.raises(deproi.IntegrationError):
            client.monitor("1")
        with pytest.raises(deproi.IntegrationError, match="not attempted"):
            client.monitor("2")
        assert len(opener.requests) == 1

    def test_http_error_does_not_trip_the_breaker(self):
        opener = FakeOpener({"monitors": http_error(404)})
        client = self.client(opener)
        for _ in range(2):
            with pytest.raises(deproi.IntegrationError, match="HTTP 404"):
                client.monitor("1")
        assert len(opener.requests) == 2

    def test_empty_releases_is_not_success(self):
        client = self.client(FakeOpener({"releases": {"releases": []}}))
        with pytest.raises(deproi.IntegrationError, match="nothing registered"):
            client.register_release(COMMIT)


class TestBetterStackInTheDeploy:
    def overrides(self, path):
        return {
            "integrations": {
                "betterstack": {
                    "credentials_file": path,
                    "monitors": ["1"],
                    "errors": {"application_id": "9", "environment": "production"},
                }
            }
        }

    def test_monitors_are_protected_only_around_recreation(self, run, tmp_path):
        opener = FakeOpener({"monitors/1": {"data": {"attributes": {"confirmation_period": 0}}}})
        path = credentials(
            tmp_path, "bs.env", BETTERSTACK_UPTIME_TOKEN=TOKEN, BETTERSTACK_ERRORS_TOKEN="errors-token-456"
        )
        run(overrides=self.overrides(path), integrations=integrations_with(opener))
        patches = [r.body for r in opener.requests if r.method == "PATCH"]
        assert patches == [{"confirmation_period": 1200}, {"confirmation_period": 0}]
        line = run.line("betterstack: ")
        assert "1 monitors protected during recreation and restored" in line
        assert f"release {COMMIT} registered in the background" in line
        assert TOKEN not in run.out

    def test_off_without_credentials(self, run, tmp_path):
        run(overrides=self.overrides(str(tmp_path / "missing.env")), integrations=integrations_with(FakeOpener()))
        assert run.line("betterstack: ").startswith("betterstack: off on this server")
        assert run.code == 0

    def test_never_changes_the_outcome(self, run, tmp_path):
        opener = FakeOpener({"betterstack.com": urllib.error.URLError("down")})
        path = credentials(tmp_path, "bs.env", BETTERSTACK_UPTIME_TOKEN=TOKEN)
        run(overrides=self.overrides(path), integrations=integrations_with(opener))
        assert run.code == 0
        assert "failed to protect" in run.line("betterstack: ")


class TestPostDeploy:
    def cfg(self, tmp_path):
        return make_config(tmp_path, {"hooks": {"post_deploy": [{"name": "warm", "command": ["warm", "cache"]}]}})

    def test_runs_hooks_and_records(self, tmp_path):
        cfg = self.cfg(tmp_path)
        executor = FakeExecutor({"{{.Config.Image}}": R(0, f"myapp:{COMMIT}\n")})
        record_path = str(tmp_path / "post.json")
        record = deproi.post_deploy(cfg, executor, None, COMMIT, record_path)
        assert record["hooks"] == [{"name": "warm", "ok": True}]
        assert record["release"] == {"ok": False, "off": True}
        hook = executor.commands("warm cache")[0]
        assert "--name" in hook and "deproi-myapp-prod-post-warm" in hook
        assert deproi.read_json(record_path)["commit"] == COMMIT

    def test_skips_when_a_newer_version_is_live(self, tmp_path):
        cfg = self.cfg(tmp_path)
        executor = FakeExecutor({"{{.Config.Image}}": R(0, "myapp:999999999999\n")})
        record = deproi.post_deploy(cfg, executor, None, COMMIT, str(tmp_path / "post.json"))
        assert record == {"commit": COMMIT, "skipped": True, "live": "999999999999"}
        assert not executor.commands("warm")

    def test_timeout_removes_the_container(self, tmp_path):
        cfg = self.cfg(tmp_path)
        executor = FakeExecutor({"warm cache": R(124, ""), "{{.Config.Image}}": R(0, f"myapp:{COMMIT}\n")})
        record = deproi.post_deploy(cfg, executor, None, COMMIT, str(tmp_path / "post.json"))
        assert record["hooks"][0]["ok"] is False
        assert len(executor.commands("rm -f deproi-myapp-prod-post-warm")) == 2

    def test_summary_shows_the_previous_post_deploy(self, run):
        cfg = self.cfg(run.tmp_path)
        deproi.write_json(
            f"{cfg.state_dir}/post-deploy.json",
            {"commit": PREVIOUS, "release": {"ok": True}, "hooks": [{"name": "warm", "ok": False, "reason": "exit 1"}]},
        )
        run(cfg=cfg)
        assert run.line("post_deploy: ") == (
            f"post_deploy: post-deploy of {COMMIT} in the background "
            f"(previous deploy {PREVIOUS}: release registered, warm failed (exit 1))"
        )

    def test_background_work_runs_the_post_deploy(self, run):
        cfg = self.cfg(run.tmp_path)
        run(FakeExecutor({"{{.Config.Image}}": R(0, f"myapp:{COMMIT}\n")}), cfg=cfg)
        record = run.background[0]()
        assert record["commit"] == COMMIT


class FakeProcess:
    def __init__(self, pids):
        self.pids = list(pids)
        self.events = []

    def fork(self):
        pid = self.pids.pop(0)
        self.events.append(f"fork:{pid}")
        return pid

    def wait(self, pid):
        self.events.append(f"wait:{pid}")

    def setsid(self):
        self.events.append("setsid")

    def isolate(self):
        self.events.append("isolate")

    def exit(self):
        self.events.append("exit")


class TestDetach:
    def test_parent_waits_for_the_child_and_returns(self, tmp_path):
        process = FakeProcess([42])
        deproi.detach(lambda: pytest.fail("parent must not work"), make_config(tmp_path), process)
        assert process.events == ["fork:42", "wait:42"]

    def test_grandchild_works_under_the_post_lock(self, tmp_path):
        done, locks = [], []
        process = FakeProcess([0, 0])
        cfg = make_config(tmp_path)
        deproi.detach(lambda: done.append(1), cfg, process, lock=lambda path, wait: locks.append(path) or 7)
        assert done == [1] and locks == [cfg.post_lock_path]
        assert process.events == ["fork:0", "setsid", "fork:0", "isolate", "exit"]

    def test_grandchild_gives_up_when_the_lock_is_busy(self, tmp_path):
        executor = FakeExecutor()
        process = FakeProcess([0, 0])
        deproi.detach(
            lambda: pytest.fail("must not run"), make_config(tmp_path), process, executor, lock=lambda path, wait: None
        )
        assert "held the lock" in executor.commands("logger")[0][-1]


class TestMessages:
    def placeholders(self, text):
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    def test_every_language_has_every_message_with_the_same_placeholders(self):
        english = deproi.MESSAGES["en"]
        for language, messages in deproi.MESSAGES.items():
            assert set(messages) == set(english), language
            for key, text in messages.items():
                assert self.placeholders(text) == self.placeholders(english[key]), (language, key)

    def test_every_message_key_used_in_the_code_exists(self):
        from conftest import ROOT

        source = (ROOT / "deproi.py").read_text()
        used = set(re.findall(r"\bt\(\s*\"([a-z_]+)\"", source))
        assert used - set(deproi.MESSAGES["en"]) == set()

    def test_fallback_to_english(self, monkeypatch):
        monkeypatch.setattr(deproi, "LANGUAGE", "xx")
        assert deproi.t("no_arguments") == "This command accepts no arguments."
