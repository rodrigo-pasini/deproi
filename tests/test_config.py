"""The server config: /etc/deproi/<name>.json, validated strictly."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
from conftest import BASE_CONFIG, make_config

import deproi


def parse(data, name="myapp-prod", **kwargs):
    return deproi.parse_config(data, name, home_of=lambda user: f"/home/{user}", **kwargs)


def with_changes(**changes):
    data = copy.deepcopy(BASE_CONFIG)
    data.update(changes)
    return data


def error_of(data) -> str:
    with pytest.raises(deproi.ConfigError) as caught:
        parse(data)
    return str(caught.value)


class TestDefaults:
    def test_minimal_config(self):
        cfg = parse(
            {
                "name": "myapp-prod",
                "checkout": {"path": "/srv/app", "owner": "deployer", "branch": "main"},
                "compose": {"project": "myapp-prod", "web_service": "web", "image": "myapp"},
            }
        )
        assert cfg.language == "en"
        assert cfg.remote == "origin"
        assert cfg.compose_files == ("compose.yaml",)
        assert cfg.env_file is None and cfg.secrets_file is None
        assert cfg.profiles == () and cfg.service_suffix is None
        assert cfg.tag_variables == ("DEPROI_TAG",)
        assert cfg.script_path == "deploy/deproi.py"
        assert (cfg.lock_timeout, cfg.build_timeout, cfg.migrations_timeout, cfg.health_timeout) == (
            1800,
            2400,
            2400,
            240,
        )
        assert cfg.min_free_bytes == 5 * 1024**3
        assert cfg.low_priority is True and cfg.pull is False
        assert all(cfg.hooks[point] == () for point in deproi.HOOK_POINTS)
        assert cfg.protected == () and cfg.betterstack is None and cfg.cloudflare is None and cfg.webhook is None
        assert cfg.checkout_home == "/home/deployer"

    def test_derived_paths_come_from_the_name(self, tmp_path):
        cfg = make_config(tmp_path)
        assert cfg.lock_path == str(tmp_path / "lock" / "deproi-myapp-prod.lock")
        assert cfg.post_lock_path == str(tmp_path / "lock" / "deproi-myapp-prod-post.lock")
        assert cfg.state_dir == str(tmp_path / "state" / "myapp-prod")
        assert cfg.syslog_tag == "deproi-myapp-prod"
        assert cfg.manual_command == "sudo /usr/local/sbin/deproi-myapp-prod"

    def test_schema_key_is_allowed(self):
        assert parse(with_changes(**{"$schema": "https://example.com/schema.json"})).name == "myapp-prod"


class TestRejections:
    def test_unknown_top_level_key(self):
        assert error_of(with_changes(colour="blue")) == "unknown key colour"

    def test_unknown_nested_key_is_named_with_its_path(self):
        data = with_changes()
        data["compose"]["profile"] = "prod"  # typo of "profiles"
        assert error_of(data) == "unknown key compose.profile"

    def test_name_must_match_the_installed_command(self):
        assert "deproi-myapp-prod" in error_of(with_changes(name="myapp-test"))

    def test_unsupported_config_version(self):
        assert "config_version 2" in error_of(with_changes(config_version=2))

    def test_unknown_language(self):
        assert "language" in error_of(with_changes(language="fr"))

    def test_owner_root_is_refused(self):
        data = with_changes()
        data["checkout"]["owner"] = "root"
        assert "must not be root" in error_of(data)

    def test_owner_must_exist(self):
        def missing(user):
            raise KeyError(user)

        with pytest.raises(deproi.ConfigError, match="does not exist"):
            deproi.parse_config(copy.deepcopy(BASE_CONFIG), "myapp-prod", home_of=missing)

    def test_checkout_path_must_be_absolute(self):
        data = with_changes()
        data["checkout"]["path"] = "srv/app"
        assert "absolute" in error_of(data)

    @pytest.mark.parametrize("path", ["../outside.yaml", "/etc/compose.yaml"])
    def test_compose_files_stay_inside_the_checkout(self, path):
        data = with_changes()
        data["compose"]["files"] = [path]
        assert "inside the checkout" in error_of(data)

    def test_missing_required_key(self):
        data = with_changes()
        del data["compose"]["web_service"]
        assert error_of(data) == "compose.web_service is required"

    @pytest.mark.parametrize("value", [0, -5, "60", True])
    def test_timeouts_must_be_positive_integers(self, value):
        assert "positive integer" in error_of(with_changes(timeouts={"health": value}))

    def test_image_without_tag(self):
        data = with_changes()
        data["compose"]["image"] = "myapp:latest"
        assert "without a tag" in error_of(data)

    def test_web_service_cannot_be_protected(self):
        data = with_changes(protected_services=[{"service": "web-prod", "busy_check": ["true"]}])
        assert "cannot be a protected service" in error_of(data)


class TestHooks:
    def test_hooks_are_parsed_with_per_point_defaults(self):
        cfg = parse(
            with_changes(
                hooks={
                    "pre_migrate": [{"name": "check", "command": ["python", "manage.py", "check"]}],
                    "migrate": [{"name": "migrate", "command": ["python", "manage.py", "migrate"], "env": {"A": "1"}}],
                    "post_migrate": [{"name": "flags", "command": ["sync"]}],
                    "post_deploy": [{"name": "warm", "command": ["warm"], "service": "worker-prod", "timeout": 60}],
                }
            )
        )
        assert cfg.hooks["pre_migrate"][0].on_failure == "fail"
        assert cfg.hooks["migrate"][0].env == (("A", "1"),)
        assert cfg.hooks["post_migrate"][0].on_failure == "warn"
        assert cfg.hooks["post_deploy"][0].service == "worker-prod"
        assert cfg.hooks["post_deploy"][0].timeout == 60
        assert cfg.hooks["migrate"][0].service == "web-prod"

    def test_command_must_be_a_list_not_a_shell_string(self):
        assert "list of strings" in error_of(with_changes(hooks={"migrate": [{"name": "m", "command": "migrate"}]}))

    def test_post_deploy_hooks_can_only_warn(self):
        data = with_changes(hooks={"post_deploy": [{"name": "x", "command": ["x"], "on_failure": "fail"}]})
        assert "on_failure must be one of warn" in error_of(data)

    def test_repeated_names(self):
        hook = {"name": "x", "command": ["x"]}
        assert "repeated names" in error_of(with_changes(hooks={"migrate": [hook, hook]}))

    @pytest.mark.parametrize("name", ["Check", "has space", ""])
    def test_hook_names_are_slugs(self, name):
        assert "hooks.migrate[0].name" in error_of(with_changes(hooks={"migrate": [{"name": name, "command": ["x"]}]}))

    def test_env_values_must_be_strings(self):
        data = with_changes(hooks={"migrate": [{"name": "m", "command": ["m"], "env": {"A": 1}}]})
        assert "env" in error_of(data)

    def test_unknown_hook_point(self):
        assert error_of(with_changes(hooks={"before_build": []})) == "unknown key hooks.before_build"


class TestIntegrations:
    def test_cloudflare_hosts_default_to_the_url_host(self):
        cfg = parse(
            with_changes(integrations={"cloudflare": {"credentials_file": "/etc/deproi/cf.env", "zone_id": "0" * 32}})
        )
        assert cfg.cloudflare.hosts == ("app.example.com",)

    def test_cloudflare_zone_is_validated(self):
        data = with_changes(integrations={"cloudflare": {"credentials_file": "/etc/x", "zone_id": "../zones"}})
        assert "zone id" in error_of(data)

    def test_cloudflare_needs_hosts_without_url(self):
        data = with_changes(url=None, integrations={"cloudflare": {"credentials_file": "/etc/x", "zone_id": "f" * 32}})
        assert "hosts is required" in error_of(data)

    def test_betterstack_ids_are_numeric(self):
        data = with_changes(integrations={"betterstack": {"credentials_file": "/etc/x", "monitors": ["abc"]}})
        assert "numeric" in error_of(data)

    def test_betterstack_errors_need_application_and_environment(self):
        data = with_changes(
            integrations={"betterstack": {"credentials_file": "/etc/x", "errors": {"application_id": "12"}}}
        )
        assert "environment is required" in error_of(data)

    def test_credentials_file_must_be_absolute(self):
        data = with_changes(integrations={"webhook": {"url_file": "webhook.env"}})
        assert "absolute" in error_of(data)

    def test_webhook_format_and_events(self):
        assert "format" in error_of(with_changes(integrations={"webhook": {"url_file": "/x", "format": "teams"}}))
        assert "events" in error_of(with_changes(integrations={"webhook": {"url_file": "/x", "events": ["start"]}}))

    def test_full_integrations(self):
        cfg = parse(
            with_changes(
                integrations={
                    "betterstack": {
                        "credentials_file": "/etc/bs",
                        "monitors": ["1", "2"],
                        "grace_period": 600,
                        "errors": {"application_id": "9", "environment": "production"},
                    },
                    "webhook": {"url_file": "/etc/wh", "format": "slack", "events": ["failure"]},
                }
            )
        )
        assert cfg.betterstack.monitors == ("1", "2")
        assert cfg.betterstack.grace_period == 600
        assert cfg.betterstack.errors_application == "9"
        assert cfg.webhook.events == ("failure",)


class TestTrust:
    def stat(self, uid=0, mode=0o100644):
        return lambda path: SimpleNamespace(st_uid=uid, st_mode=mode if not path.endswith("/etc") else 0o040755)

    def test_root_owned_file_is_trusted(self):
        assert deproi.check_root_owned("/x", stat_fn=self.stat()) is None

    @pytest.mark.parametrize(("uid", "mode"), [(1000, 0o100644), (0, 0o100664), (0, 0o100646)])
    def test_not_root_or_writable_by_others(self, uid, mode):
        assert "owned by root" in deproi.check_root_owned("/x", stat_fn=self.stat(uid, mode))

    def test_secret_files_must_not_be_readable_by_others(self):
        assert deproi.check_root_owned("/x", secret=True, stat_fn=self.stat(0, 0o100644))
        assert deproi.check_root_owned("/x", secret=True, stat_fn=self.stat(0, 0o100600)) is None

    def test_missing_file(self):
        def missing(path):
            raise FileNotFoundError(path)

        assert "missing or unreadable" in deproi.check_root_owned("/x", stat_fn=missing)

    def write(self, tmp_path, content):
        (tmp_path / "myapp-prod.json").write_text(content)

    def load(self, tmp_path, stat_fn):
        return deproi.load_config(
            "myapp-prod", config_dir=str(tmp_path), stat_fn=stat_fn, home_of=lambda user: "/home/x"
        )

    def test_load_config_reads_a_trusted_file(self, tmp_path):
        self.write(tmp_path, json.dumps(BASE_CONFIG))
        safe = lambda path: SimpleNamespace(st_uid=0, st_mode=0o040755 if path == str(tmp_path) else 0o100600)  # noqa: E731
        assert self.load(tmp_path, safe).project == "myapp-prod"

    def test_load_config_refuses_an_insecure_directory(self, tmp_path):
        self.write(tmp_path, json.dumps(BASE_CONFIG))
        loose = lambda path: SimpleNamespace(st_uid=0, st_mode=0o040777 if path == str(tmp_path) else 0o100600)  # noqa: E731
        with pytest.raises(deproi.ConfigError, match="owned by root"):
            self.load(tmp_path, loose)

    def test_load_config_refuses_invalid_json(self, tmp_path):
        self.write(tmp_path, "{ not json")
        safe = lambda path: SimpleNamespace(st_uid=0, st_mode=0o040755 if path == str(tmp_path) else 0o100600)  # noqa: E731
        with pytest.raises(deproi.ConfigError, match="not valid JSON"):
            self.load(tmp_path, safe)

    def test_load_config_refuses_a_file_owned_by_a_user(self, tmp_path):
        self.write(tmp_path, json.dumps(BASE_CONFIG))
        with pytest.raises(deproi.ConfigError, match="owned by root"):
            self.load(tmp_path, lambda path: SimpleNamespace(st_uid=1000, st_mode=0o100600))


def test_schema_file_lists_every_top_level_key():
    """deproi.schema.json documents exactly the keys the script accepts."""
    from conftest import ROOT

    schema = json.loads((ROOT / "deproi.schema.json").read_text())
    accepted = {
        "$schema",
        "config_version",
        "name",
        "language",
        "checkout",
        "compose",
        "url",
        "script_path",
        "docs",
        "timeouts",
        "build",
        "health_interval",
        "min_free_disk_gb",
        "hooks",
        "protected_services",
        "integrations",
    }
    assert set(schema["properties"]) == accepted
    assert schema["additionalProperties"] is False
