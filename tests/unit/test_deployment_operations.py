import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


def _load(name: str) -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "ops" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"ops_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


preflight = _load("deployment_preflight")
restore = _load("restore_drill")
soak = _load("zalo_soak")


def configuration() -> dict[str, Any]:
    env = {
        "NODE_ENV": "production",
        "WEB_AUTH_MODE": "trusted_header",
        "WEB_BIND": "0.0.0.0",
        "WEB_AUTH_ISSUER": "https://identity.example.invalid",
        "WEB_AUTH_HEADER_SECRET": "s" * 32,
        "OPENAI_API_KEY": "synthetic",
        "EMBEDDING_PROVIDER": "fake",
        "EMBEDDING_API_KEY": "fake",
        "EMBEDDING_MODEL": "fake",
        "EMBEDDING_DIM": "1024",
        "RERANK_PROVIDER": "fake",
        "RERANK_API_KEY": "fake",
        "RERANK_MODEL": "fake",
        "RERANK_MIN_SCORE": "0.45",
        "DAILY_BUDGET_USD": "1",
        "BOT_MENTION_NAME": "Synthetic",
        "ZALO_MODE": "polling",
        "DATABASE_URL": "postgresql://bot:synthetic-password@postgres:5432/chatbot",
        "REDIS_URL": "redis://redis:6379/0",
    }
    return {
        "services": {
            "postgres": {"environment": {"POSTGRES_PASSWORD": "synthetic-password"}},
            "redis": {},
            "api": {"environment": dict(env), "ports": [{"host_ip": "127.0.0.1"}]},
            "worker": {"environment": dict(env)},
            "maintenance": {"environment": dict(env)},
        }
    }


def test_production_data_services_are_private_and_urls_consistent() -> None:
    config = configuration()
    assert preflight.validate_config(config) == []
    config["services"]["postgres"]["ports"] = [{"host_ip": "127.0.0.1"}]
    assert any("publication forbidden" in item for item in preflight.validate_config(config))


def test_url_encoded_password_matches_data_service() -> None:
    config = configuration()
    config["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"] = "complex:@password"
    for name in ("api", "worker", "maintenance"):
        config["services"][name]["environment"]["DATABASE_URL"] = (
            "postgresql://bot:complex%3A%40password@postgres:5432/chatbot"
        )
    assert preflight.validate_config(config) == []


def test_failures_do_not_echo_config_secrets() -> None:
    config = configuration()
    env = config["services"]["api"]["environment"]
    env.update(WEB_AUTH_MODE="dev", WEB_AUTH_HEADER_SECRET="private-marker", DAILY_BUDGET_USD="bad")
    issues = preflight.validate_config(config)
    assert any("trusted_header" in item for item in issues)
    assert "private-marker" not in json.dumps(issues)
    assert "postgresql://" not in json.dumps(issues)


def test_expected_polling_requires_profile_and_valid_token() -> None:
    config = configuration()
    for name in ("api", "worker", "maintenance"):
        config["services"][name]["environment"].update(
            ZALO_POLLING_EXPECTED="true", ZALO_BOT_TOKEN="synthetic-no-network"
        )
    assert any("--zalo" in issue for issue in preflight.validate_config(config))
    config["services"]["zalo"] = {"environment": dict(config["services"]["worker"]["environment"])}
    assert preflight.validate_config(config) == []
    config["services"]["api"]["environment"]["ZALO_BOT_TOKEN"] = ""
    assert any("invalid settings" in issue for issue in preflight.validate_config(config))


def test_polling_profile_cannot_be_silently_unmonitored() -> None:
    config = configuration()
    config["services"]["zalo"] = {"environment": dict(config["services"]["worker"]["environment"])}
    assert any("ZALO_POLLING_EXPECTED" in issue for issue in preflight.validate_config(config))


def test_dev_only_publishes_loopback_and_rejects_container_dev_auth() -> None:
    config: dict[str, Any] = {
        "services": {
            "postgres": {
                "environment": {"POSTGRES_PASSWORD": "dev"},
                "ports": [{"host_ip": "127.0.0.1"}],
            },
            "redis": {"ports": [{"host_ip": "127.0.0.1"}]},
        }
    }
    assert preflight.validate_config(config, development=True) == []
    config["services"]["redis"]["ports"] = [{"host_ip": "0.0.0.0"}]
    config["services"]["api"] = {}
    assert len(preflight.validate_config(config, development=True)) == 2


def test_receiver_comes_from_operator_file_and_rejects_fake_contact(tmp_path: Path) -> None:
    secret = tmp_path / "receiver"
    config = {
        "services": {"prometheus": {}, "alertmanager": {}},
        "secrets": {
            "alert_webhook_url": {"file": str(secret)},
        },
    }
    secret.write_text("https://operator.example.invalid/secret-path", encoding="utf-8")
    assert preflight.validate_alert_receiver(config) == []
    secret.write_text("http://localhost:3000/api/health", encoding="utf-8")
    issues = preflight.validate_alert_receiver(config)
    assert issues and "secret-path" not in str(issues)


def test_backup_type_and_target_are_verified_before_any_docker_command(tmp_path: Path) -> None:
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"plain SQL")
    with pytest.raises(ValueError, match="custom format"):
        restore.validate_backup(archive)
    archive.write_bytes(b"PGDMPsynthetic-header")
    assert restore.validate_backup(archive) == archive.resolve()
    with pytest.raises(ValueError):
        restore.start_command(archive, "existing-production-container", "b" * 32)
    command = restore.start_command(archive.resolve(), restore.container_name("a" * 32), "b" * 32)
    assert command[command.index("--network") + 1] == "none"
    assert "--volume" not in command and "--publish" not in command
    assert any("target=/backup.dump,readonly" in part for part in command)


def test_restore_failure_cleans_up_only_generated_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"PGDMPsynthetic-header")
    commands: list[list[str]] = []

    def execute(command: list[str], **_kwargs: Any) -> str:
        commands.append(command)
        if "pg_restore" in command:
            raise RuntimeError("simulated restore failure")
        return "synthetic-container"

    monkeypatch.setattr(restore, "_run", execute)

    def process(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        if "inspect" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps([inspection(commands[0])]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(restore.subprocess, "run", process)
    with pytest.raises(restore.ArchiveRestoreError):
        restore.execute_drill(archive)
    created_name = commands[0][commands[0].index("--name") + 1]
    assert commands[-1] == ["docker", "rm", "--force", "--volumes", "c" * 64]
    assert created_name.startswith("cp-restore-drill-")
    assert not any("postgresql://" in item for command in commands for item in command)


def inspection(command: list[str]) -> dict[str, Any]:
    name = command[command.index("--name") + 1]
    labels = dict(
        command[index + 1].split("=", 1)
        for index, value in enumerate(command)
        if value == "--label"
    )
    return {
        "Name": f"/{name}",
        "Id": "c" * 64,
        "Config": {"Image": restore.IMAGE, "Labels": labels},
        "HostConfig": {"NetworkMode": "none"},
    }


def test_timeout_after_creation_still_inspects_and_cleans_its_own_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"PGDMPsynthetic-header")
    commands: list[list[str]] = []

    def execute(command: list[str], **_kwargs: Any) -> str:
        commands.append(command)
        if "run" in command:
            raise subprocess.TimeoutExpired(command, timeout=300)
        return ""

    monkeypatch.setattr(restore, "_run", execute)
    monkeypatch.setattr(
        restore.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps([inspection(commands[0])])
        ),
    )
    with pytest.raises(subprocess.TimeoutExpired):
        restore.execute_drill(archive)
    assert commands[-1] == ["docker", "rm", "--force", "--volumes", "c" * 64]


@pytest.mark.parametrize("mismatch", ["name", "image", "marker", "network", "id"])
def test_cleanup_refuses_any_unverified_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    name, marker = restore.container_name("a" * 32), "b" * 32
    container = inspection(restore.start_command(tmp_path / "backup.dump", name, marker))
    if mismatch == "name":
        container["Name"] = "/production"
    elif mismatch == "image":
        container["Config"]["Image"] = "production-image"
    elif mismatch == "marker":
        container["Config"]["Labels"][f"{restore.LABEL_PREFIX}.marker"] = "other-task"
    elif mismatch == "network":
        container["HostConfig"]["NetworkMode"] = "production-network"
    else:
        container["Id"] = "arbitrary-target"
    removed: list[list[str]] = []
    monkeypatch.setattr(
        restore.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps([container])),
    )
    monkeypatch.setattr(restore, "_run", lambda command, **_kwargs: removed.append(command))
    with pytest.raises(ValueError, match="refuse cleanup"):
        restore.cleanup_container(name, marker)
    assert removed == []


def test_preflight_custom_env_file_is_also_the_runtime_app_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "private-runtime.env"
    path.write_text("PRIVATE_KEY=synthetic-secret-marker\n", encoding="utf-8")
    configuration = {
        "services": {
            "postgres": {"environment": {"POSTGRES_PASSWORD": "dev"}},
            "redis": {},
        }
    }
    captured: dict[str, Any] = {}

    def resolve(command: list[str], **kwargs: Any) -> SimpleNamespace:
        captured.update(command=command, environment=kwargs["env"])
        return SimpleNamespace(returncode=0, stdout=json.dumps(configuration))

    monkeypatch.setattr(preflight.subprocess, "run", resolve)
    monkeypatch.setattr(sys, "argv", ["preflight", "--development", "--env-file", str(path)])
    assert preflight.main() == 0
    assert captured["environment"]["APP_ENV_FILE"] == str(path.resolve())
    assert captured["command"][captured["command"].index("--env-file") + 1] == str(path.resolve())
    assert "synthetic-secret-marker" not in capsys.readouterr().out


@pytest.mark.parametrize("password", ["", "short-password", "a" * 16, "$(printf secret-marker)"])
def test_grafana_runtime_guard_rejects_weak_password_without_printing_it(password: str) -> None:
    source = (Path(__file__).resolve().parents[2] / "ops/docker-compose.yml").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"entrypoint:\n      - /bin/sh\n      - -ec\n      - \|\n(.*?)      - cp-grafana",
        source,
        re.S,
    )
    assert match
    # Run the actual guard; replace only dispatch to the unavailable Grafana binary.
    script = textwrap.dedent(match[1]).replace("$$", "$")
    script = script.replace('exec /run.sh "$@"', "printf 'guard-passed\\n'")
    shell = shutil.which("sh") or "C:/Program Files/Git/bin/sh.exe"
    assert Path(shell).is_file(), "POSIX shell is required to verify the container startup guard"
    result = subprocess.run(
        [shell, "-ec", script],
        capture_output=True,
        text=True,
        timeout=5,
        env={**os.environ, "GF_SECURITY_ADMIN_PASSWORD": password},
        check=False,
    )
    assert result.returncode == (0 if len(password) >= 16 else 1)
    assert "secret-marker" not in result.stdout + result.stderr
    if len(password) >= 16:
        assert result.stdout == "guard-passed\n"


def test_synthetic_junit_summary_does_not_copy_failure_payload(tmp_path: Path) -> None:
    junit = tmp_path / "cycle.xml"
    junit.write_text(
        '<testsuites><testsuite><testcase name="failure"><failure message="private payload"/>'
        '</testcase><testcase name="skip"><skipped/></testcase></testsuite></testsuites>',
        encoding="utf-8",
    )
    assert soak.read_cycle(junit) == {"tests": 2, "failures": 1, "errors": 0, "skipped": 1}


def test_committed_base_has_no_data_ports_and_dev_override_is_loopback_only() -> None:
    # Limit this structural check to the repository's simple service blocks; actual
    # merged/expanded configuration must still pass Docker preflight on deployment.
    root = Path(__file__).resolve().parents[2]
    source = (root / "ops/docker-compose.yml").read_text(encoding="utf-8")
    for name in ("postgres", "redis"):
        body = re.split(r"(?m)^  [a-z_]+:\s*$", source.split(f"\n  {name}:\n", 1)[1], maxsplit=1)[0]
        assert "ports:" not in body and "<<:" not in body
    override = (root / "ops/docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:5432:5432" in override and "127.0.0.1:6379:6379" in override
    assert "0.0.0.0" not in override
    assert "WEB_AUTH_MODE: trusted_header" in source
    assert "NODE_ENV: production" in source
