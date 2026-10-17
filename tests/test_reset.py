import importlib

import pytest


def reset_module():
    try:
        return importlib.import_module("juya_api.operations.reset")
    except ImportError:
        pytest.fail("Scoped, inventory-bound legacy reset is not implemented")


def inventory():
    return {
        "containers": [
            {"name": "juya-admin-small-admin-api-1", "image": "juya-admin-api-test:known"},
            {"name": "juya-admin-small-mysql-1", "image": "mysql:8.4"},
        ],
        "volumes": [{"Name": "juya-admin-small_mysql_data"}],
        "databases": {"names": ["information_schema", "juya", "mysql", "sys"]},
    }


def test_reset_plan_names_only_inventoried_legacy_resources():
    plan = reset_module().make_reset_plan(inventory())
    assert plan["containers"] == ["juya-admin-small-admin-api-1", "juya-admin-small-mysql-1"]
    assert plan["volumes"] == ["juya-admin-small_mysql_data"]
    assert plan["database_names"] == ["juya"]
    assert "mysql" not in plan["database_names"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("containers", [{"name": "another-project-api", "image": "unrelated"}]),
        ("volumes", [{"Name": "juya-production_mysql_data"}]),
        ("volumes", [{"Name": "*"}]),
        ("containers", [{"name": "juya-rebuild-mysql-verify", "image": "mysql:8.4"}]),
    ],
)
def test_reset_refuses_new_or_unrelated_resources(field, value):
    data = inventory()
    data[field] = value
    with pytest.raises(ValueError):
        reset_module().make_reset_plan(data)


def test_reset_rejects_an_unreviewed_additional_business_database():
    data = inventory()
    data["databases"]["names"].append("another_application")
    with pytest.raises(ValueError):
        reset_module().make_reset_plan(data)
