"""Validate resolved Docker configuration without exposing its secrets.

This is a local configuration check, not OIDC/restore/notification acceptance.
Docker output is captured in memory; neither rendered config nor stderr is printed.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydantic import ValidationError

from config.schema import Settings

ROOT = Path(__file__).resolve().parents[1]
APP_SERVICES = ("api", "worker", "maintenance", "zalo")


def _loopback(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def validate_config(config: dict[str, Any], *, development: bool = False) -> list[str]:
    """Only return constant messages/field names, never config values or credentials."""
    issues: list[str] = []
    services = config.get("services", {})
    for name in ("postgres", "redis"):
        service = services.get(name, {})
        if name not in services:
            issues.append(f"missing data service: {name}")
        for port in service.get("ports", []):
            if not development or not _loopback(str(port.get("host_ip", ""))):
                issues.append(f"{name}: host publication forbidden outside loopback dev")
    password = services.get("postgres", {}).get("environment", {}).get("POSTGRES_PASSWORD", "")
    if not password or (not development and password in {"bot", "postgres", "password"}):
        issues.append("postgres: configure a non-default password")
    if development:
        if any(name in services for name in APP_SERVICES):
            issues.append("dev: run API/workers natively; do not enable container app profiles")
        return issues

    for name in ("api", "worker", "maintenance"):
        if name not in services:
            issues.append(f"missing production app service: {name}")
    for name in APP_SERVICES:
        if name not in services:
            continue
        service = services[name]
        env = service.get("environment", {})
        if env.get("NODE_ENV") != "production" or env.get("WEB_AUTH_MODE") != "trusted_header":
            issues.append(f"{name}: production requires trusted_header auth")
        try:
            # BaseSettings' runtime-only option is absent from its mypy-generated signature.
            Settings(**env, _env_file=None)  # type: ignore[call-arg]
        except ValidationError as error:
            fields = sorted(
                {str(item["loc"][0]) if item["loc"] else "validator" for item in error.errors()}
            )
            issues.append(f"{name}: invalid settings fields: {', '.join(fields)}")
        try:
            database = urlsplit(str(env.get("DATABASE_URL", "")))
            redis = urlsplit(str(env.get("REDIS_URL", "")))
            if (
                database.hostname != "postgres"
                or database.path != "/chatbot"
                or database.username != "bot"
                or database.port not in {None, 5432}
            ):
                issues.append(
                    f"{name}: bundled deployment DATABASE_URL must target postgres/chatbot"
                )
            if unquote(database.password or "") != password:
                issues.append(f"{name}: database password differs from postgres service")
            if redis.hostname != "redis" or redis.port not in {None, 6379}:
                issues.append(f"{name}: bundled deployment REDIS_URL must target redis")
        except ValueError:
            issues.append(f"{name}: invalid data service URLs")
        for port in service.get("ports", []):
            if not _loopback(str(port.get("host_ip", ""))):
                issues.append(f"{name}: app ports must be host-loopback only")
    expected = str(
        services.get("api", {}).get("environment", {}).get("ZALO_POLLING_EXPECTED", "false")
    ).lower() in {"1", "true", "yes", "on"}
    if expected and "zalo" not in services:
        issues.append("zalo: expected polling requires --zalo in this bundled deployment plan")
    if "zalo" in services and not expected:
        issues.append("zalo: enable ZALO_POLLING_EXPECTED when starting the polling profile")
    if "grafana" in services:
        env = services["grafana"].get("environment", {})
        if env.get("GF_AUTH_ANONYMOUS_ENABLED") != "false":
            issues.append("grafana: anonymous access must be disabled")
        if len(str(env.get("GF_SECURITY_ADMIN_PASSWORD", ""))) < 16:
            issues.append("grafana: set an operator password of at least 16 characters")
    if "prometheus" in services:
        token = services.get("api", {}).get("environment", {}).get("METRICS_SCRAPE_TOKEN", "")
        if len(str(token)) < 32:
            issues.append(
                "monitoring: configure the shared metrics token of at least 32 characters"
            )
    for name in ("prometheus", "grafana", "alertmanager"):
        for port in services.get(name, {}).get("ports", []):
            if not _loopback(str(port.get("host_ip", ""))):
                issues.append(f"{name}: monitoring ports must be host-loopback only")
    return issues


def validate_alert_receiver(config: dict[str, Any]) -> list[str]:
    services = config.get("services", {})
    if not {"prometheus", "alertmanager"} <= services.keys():
        return ["alerts: enable monitoring and alerts profiles"]
    filename = config.get("secrets", {}).get("alert_webhook_url", {}).get("file", "")
    try:
        secret_path = Path(filename).resolve(strict=True)
        if secret_path.is_relative_to(ROOT):
            return ["alerts: keep the receiver secret outside the repository"]
        receiver = urlsplit(secret_path.read_text(encoding="utf-8").strip())
        if receiver.scheme != "https" or not receiver.hostname:
            return ["alerts: receiver secret must contain an HTTPS generic webhook URL"]
        if receiver.hostname in {"localhost", "api", "grafana", "alertmanager"}:
            return ["alerts: receiver must be an operator endpoint"]
        try:
            if ipaddress.ip_address(receiver.hostname).is_loopback:
                return ["alerts: receiver must be an operator endpoint"]
        except ValueError:
            pass
    except (OSError, ValueError):
        return ["alerts: receiver secret is missing or invalid"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--require-alerts", action="store_true")
    parser.add_argument("--zalo", action="store_true", help="Include the expected polling service")
    args = parser.parse_args()
    if args.development and (args.zalo or args.require_alerts):
        parser.error("--zalo/--require-alerts apply to the bundled production profiles")
    command = [
        "docker",
        "compose",
        "--env-file",
        str(args.env_file.resolve()),
        "-f",
        str(ROOT / "ops/docker-compose.yml"),
    ]
    if args.development:
        command += ["-f", str(ROOT / "ops/docker-compose.dev.yml")]
    else:
        command += ["--profile", "app"]
        if args.zalo:
            command += ["--profile", "zalo"]
        if args.require_alerts:
            command += ["--profile", "monitoring", "--profile", "alerts"]
    command += ["config", "--format", "json"]
    try:
        environment = dict(os.environ)
        # Compose --env-file affects interpolation, not service env_file by itself.
        environment["APP_ENV_FILE"] = str(args.env_file.resolve())
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=30, check=False, env=environment
        )
        if result.returncode:
            print("Compose resolution failed; inspect private configuration locally.")
            return 1
        config = json.loads(result.stdout)
        issues = validate_config(config, development=args.development)
        if args.require_alerts:
            issues += validate_alert_receiver(config)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        print("Compose preflight unavailable: Docker/configuration could not be read.")
        return 1
    for issue in issues:
        print(issue)
    if issues:
        return 1
    print(
        "Local configuration checks passed. "
        "Proxy identity, restore and alert delivery still require operational acceptance."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
