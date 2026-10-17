"""Explicit empty-environment bootstrap; secrets stay in root-owned server files."""

import argparse
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


class SetupError(RuntimeError):
    pass


def write_private(path, content, mode=0o600):
    if path.is_symlink() or path.exists():
        raise ValueError("refusing to replace an existing infrastructure file")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)


def prepare(root, mysql_image, redis_image):
    for image in (mysql_image, redis_image):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            raise ValueError("verified immutable infrastructure image IDs are required")
    root = Path(root)
    if root.is_symlink():
        raise ValueError("infrastructure root cannot be a symlink")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_mode & 0o077:
        raise ValueError("infrastructure root must be private")
    path = root / "infrastructure-secrets.json"
    if path.exists():
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError("infrastructure state must be private")
        value = json.loads(path.read_text())
        if (
            value.get("schema_version") != 1
            or value.get("owner") != "juya-rebuild-v15"
            or value.get("mysql_image") != mysql_image
            or value.get("redis_image") != redis_image
            or set(value.get("environments", {})) != {"test", "production"}
        ):
            raise ValueError("infrastructure state or image selection mismatch")
        for environment, setting in value["environments"].items():
            if setting.get("database") != "juya_" + environment:
                raise ValueError("invalid database selection")
            for key in ("app_password", "migration_password", "redis_password", "lookup_key"):
                if not re.fullmatch(r"[a-f0-9]{64}", setting.get(key, "")):
                    raise ValueError("invalid retained secret")
        return value
    if (root / "secrets").exists():
        raise ValueError("incomplete infrastructure setup requires inspection")
    value = {
        "schema_version": 1,
        "owner": "juya-rebuild-v15",
        "mysql_image": mysql_image,
        "redis_image": redis_image,
        "root_password": secrets.token_hex(32),
        "environments": {
            environment: {
                "database": "juya_" + environment,
                "app_password": secrets.token_hex(32),
                "migration_password": secrets.token_hex(32),
                "redis_password": secrets.token_hex(32),
                "field_encryption_key": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                "lookup_key": secrets.token_hex(32),
            }
            for environment in ("test", "production")
        },
    }
    folder = root / "secrets"
    folder.mkdir(mode=0o700)
    # Docker's nonroot Redis process must read bind-mounted secret files. Their parent is0700.
    write_private(folder / "mysql-root-password", value["root_password"], 0o644)
    for environment, setting in value["environments"].items():
        password = setting["redis_password"]
        write_private(folder / f"redis-{environment}-password", password, 0o644)
        memory = "32mb" if environment == "test" else "64mb"
        write_private(
            folder / f"redis-{environment}.conf",
            "\n".join(
                [
                    "bind 0.0.0.0",
                    "protected-mode yes",
                    "port 6379",
                    "dir /data",
                    "appendonly yes",
                    "appendfsync everysec",
                    'save ""',
                    "maxmemory " + memory,
                    "maxmemory-policy noeviction",
                    "requirepass " + password,
                    "loglevel warning",
                    "",
                ]
            ),
            0o644,
        )
    write_private(path, json.dumps(value, indent=2) + "\n")
    write_private(
        root / "compose-infrastructure.env",
        "\n".join(
            [
                "JUYA_MYSQL_IMAGE=" + mysql_image,
                "JUYA_REDIS_IMAGE=" + redis_image,
                "JUYA_SECRETS_DIRECTORY=" + str(folder),
                "",
            ]
        ),
    )
    return value


def account_sql(value):
    statements = []
    for environment, setting in value["environments"].items():
        name = "juya_" + environment
        statements.append(
            f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_0900_ai_ci;"
        )
        for role, privileges in [
            ("app", "SELECT, INSERT, UPDATE, DELETE"),
            ("migration", "ALL PRIVILEGES"),
        ]:
            password = setting[role + "_password"]
            if not re.fullmatch(r"[a-f0-9]{64}", password):
                raise ValueError("invalid database secret")
            statements.extend(
                [
                    f"CREATE USER IF NOT EXISTS '{name}_{role}'@'%' IDENTIFIED BY '{password}';",
                    f"GRANT {privileges} ON `{name}`.* TO '{name}_{role}'@'%';",
                ]
            )
    return "\n".join(statements) + "\n"


def run(args, *, input=None):
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise SetupError("infrastructure command failed; inspect the selected service privately")
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql-image", required=True)
    parser.add_argument("--redis-image", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError("server root execution required")
        root = Path("/etc/juya/rebuild")
        value = prepare(root, args.mysql_image, args.redis_image)
        source, target = Path(__file__).with_name("compose-infra.yml"), root / "compose-infra.yml"
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError("infrastructure configuration changed; review it explicitly")
        if not target.exists():
            shutil.copyfile(source, target)
            target.chmod(0o600)
        command = [
            "docker",
            "compose",
            "--env-file",
            str(root / "compose-infrastructure.env"),
            "-p",
            "juya-rebuild-infra",
            "-f",
            str(target),
        ]
        run([*command, "config", "--quiet"])
        if args.apply:
            run([*command, "up", "-d", "--wait", "--wait-timeout", "90"])
            container = run([*command, "ps", "-q", "mysql"]).strip()
            if not re.fullmatch(r"[a-f0-9]{12,64}", container):
                raise ValueError("exact infrastructure MySQL container required")
            run(
                [
                    "docker",
                    "exec",
                    "-i",
                    container,
                    "sh",
                    "-ec",
                    'MYSQL_PWD="$(cat /run/secrets/mysql-root-password)" exec mysql -uroot',
                ],
                input=account_sql(value),
            )
        print(
            json.dumps(
                {
                    "prepared": True,
                    "applied": args.apply,
                    "databases": ["juya_test", "juya_production"],
                    "public_ports": 0,
                }
            )
        )
        return 0
    except Exception:
        print("Infrastructure setup failed; no credentials were printed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
