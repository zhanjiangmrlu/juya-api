"""Inventory-bound reset planning; never infer targets from wildcard prefixes."""

import hashlib
import json

LEGACY_CONTAINERS = frozenset(
    {
        "juya-admin-small-admin-api-1",
        "juya-admin-small-admin-worker-1",
        "juya-admin-small-admin-beat-1",
        "juya-admin-small-mysql-1",
        "juya-admin-small-redis-1",
        "juya-miniapp-test-miniapp-api-1",
        "juya-miniapp-test-miniapp-worker-1",
        "juya-miniapp-test-miniapp-beat-1",
    }
)
LEGACY_VOLUMES = frozenset(
    {
        "juya-admin-small_mysql_data",
        "juya-admin-small_redis_data",
        "juya-admin-small_juya_imports",
    }
)
SYSTEM_DATABASES = frozenset({"mysql", "sys", "information_schema", "performance_schema"})
LEGACY_BACKUP_DIRECTORIES = (
    "/opt/juya/backups",
    "/etc/juya/backups",
    "/opt/juya/juya-admin-web-backups",
    "/opt/juya/juya-miniapp-h5-backups",
)


def make_reset_plan(inventory: dict) -> dict:
    """Reject any resource beyond the reviewed old deployment's exact allowlist."""
    containers = [item["name"] for item in inventory["containers"]]
    volumes = [item["Name"] for item in inventory["volumes"]]
    databases = sorted(set(inventory["databases"]["names"]) - SYSTEM_DATABASES)
    if not set(containers) <= LEGACY_CONTAINERS:
        raise ValueError("Unreviewed container in inventory")
    if not set(volumes) <= LEGACY_VOLUMES:
        raise ValueError("Unreviewed volume in inventory")
    if set(databases) - {"juya"}:
        raise ValueError("Unreviewed application database in inventory")
    encoded = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    return {
        "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
        "containers": containers,
        "volumes": volumes,
        "database_names": databases,
        "backup_directories": list(LEGACY_BACKUP_DIRECTORIES),
    }
