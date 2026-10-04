"""Exercise the standalone app's trust boundary, mutations and bounded snapshots."""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

APP = Path(__file__).resolve().parents[1] / "abschlagsradar_app"
sys.path.insert(0, str(APP))
from server import create_app
from settings import create_settings
from store import SnapshotStore


class FakeHA:
    def __init__(self):
        self.messages = []
        self.offline = False

    async def call(self, msg):
        self.messages.append(msg)
        if self.offline:
            raise ConnectionError("offline")
        if msg["type"] == "config/auth/list":
            return [
                {"id": "admin", "group_ids": ["system-admin"], "is_active": True},
                {"id": "reader", "group_ids": ["system-users"], "is_active": True},
            ]
        if msg["type"] == "abschlagsradar/app":
            return [{"id": "contract", "history": {"readings": []}}]
        return None

    async def rest(self, path, data=None, method=None):
        self.messages.append({"path": path, "data": data, "method": method})
        if path == "config/config_entries/flow":
            return {"flow_id": "new", "type": "menu"}
        if data == {"next_step_id": "gas"}:
            return {
                "flow_id": "new",
                "type": "form",
                "data_schema": [
                    {"name": field}
                    for field in (
                        "name",
                        "price",
                        "base",
                        "base_period",
                        "payment",
                        "payment_day",
                        "billing_start",
                        "gas_mode",
                        "gas_factor",
                        "annual_estimate",
                        "source_unit",
                        "source_sensor",
                    )
                ],
            }
        assert "energy_type" not in data
        assert "source_sensor" not in data
        assert data["gas_factor"] == 10.6
        return {"type": "create_entry", "result": {"entry_id": "gas-entry"}}


def run(coro):
    return asyncio.run(coro)


def test_ingress_peer_cannot_be_spoofed(tmp_path):
    async def check():
        client = TestClient(TestServer(create_app(FakeHA(), SnapshotStore(tmp_path / "s.db"))))
        await client.start_server()
        try:
            response = await client.get("/api/contracts", headers={"X-Remote-User-Id": "admin"})
            assert response.status == 403
        finally:
            await client.close()

    run(check())


def test_ingress_requires_identity_and_admin_for_edits(tmp_path):
    async def check():
        ha = FakeHA()
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            assert (await client.get("/api/session")).status == 403
            response = await client.get("/api/session", headers={"X-Remote-User-Id": "admin"})
            assert (await response.json())["is_admin"] is True
            response = await client.get("/api/session", headers={"X-Remote-User-Id": "reader"})
            assert (await response.json())["is_admin"] is False
            response = await client.post(
                "/api/message", headers={"X-Remote-User-Id": "reader"}, json={"type": "abschlagsradar/edit"}
            )
            assert response.status == 403
            assert not any(m["type"] == "abschlagsradar/edit" for m in ha.messages)
        finally:
            await client.close()

    run(check())


def test_only_allowlisted_budget_operations_and_no_cross_site(tmp_path):
    async def check():
        ha = FakeHA()
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            response = await client.post(
                "/api/message",
                headers={"X-Remote-User-Id": "admin"},
                json={"type": "call_service", "domain": "homeassistant", "service": "restart"},
            )
            assert response.status == 400
            assert not any(m["type"] == "call_service" for m in ha.messages)
            response = await client.post(
                "/api/message",
                headers={"X-Remote-User-Id": "admin", "Sec-Fetch-Site": "cross-site"},
                json={"type": "abschlagsradar/edit"},
            )
            assert response.status == 403
            response = await client.post(
                "/api/message",
                headers={"X-Remote-User-Id": "admin"},
                json={
                    "type": "abschlagsradar/edit",
                    "entry_id": "contract",
                    "action": "reading",
                    "payload": {"date": "2026-01-01", "value": 100},
                },
            )
            assert response.status == 200
            assert ha.messages[-1]["action"] == "reading"
        finally:
            await client.close()

    run(check())


def test_live_data_snapshot_export_and_offline_error(tmp_path):
    async def check():
        ha = FakeHA()
        store = SnapshotStore(tmp_path / "s.db")
        client = TestClient(TestServer(create_app(ha, store, {"127.0.0.1"})))
        await client.start_server()
        try:
            response = await client.get("/api/contracts", headers={"X-Remote-User-Id": "reader"})
            assert response.status == 200
            assert store.latest()["contracts"] == await response.json()
            response = await client.get("/api/export", headers={"X-Remote-User-Id": "reader"})
            assert response.status == 403
            response = await client.get("/api/export", headers={"X-Remote-User-Id": "admin"})
            assert (await response.json())["format"] == "abschlagsradar-backup"
            assert "SUPERVISOR_TOKEN" not in json.dumps(store.latest())
            ha.offline = True
            response = await client.get("/api/contracts", headers={"X-Remote-User-Id": "admin"})
            assert response.status == 503
            assert "contracts" not in await response.json()
        finally:
            await client.close()

    run(check())


def test_bounded_deduplicated_snapshots(tmp_path):
    store = SnapshotStore(tmp_path / "s.db")
    for i in range(40):
        store.save([{"value": i}])
        store.save([{"value": i}])
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 24
    assert store.latest()["contracts"] == [{"value": 39}]


def test_reverting_to_an_earlier_snapshot_is_still_the_latest(tmp_path):
    store = SnapshotStore(tmp_path / "s.db")
    store.save([{"value": "A"}])
    store.save([{"value": "B"}])
    store.save([{"value": "A"}])
    assert store.latest()["contracts"] == [{"value": "A"}]


def test_app_creates_gas_contract_through_menu_and_form(tmp_path):
    async def check():
        ha = FakeHA()
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            response = await client.post(
                "/api/contracts",
                headers={"X-Remote-User-Id": "admin"},
                json={"energy_type": "gas", "name": "Gas", "gas_factor": 10.6, "source_sensor": ""},
            )
            assert response.status == 200
            assert (await response.json())["entry_id"] == "gas-entry"
            assert ha.messages[-2]["data"] == {"next_step_id": "gas"}
        finally:
            await client.close()

    run(check())


def test_invalid_json_and_non_object_are_input_errors(tmp_path):
    async def check():
        client = TestClient(TestServer(create_app(FakeHA(), SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            for body in ("{", "[]", "null"):
                response = await client.post(
                    "/api/contracts",
                    data=body,
                    headers={"X-Remote-User-Id": "admin", "Content-Type": "application/json"},
                )
                assert response.status == 400
                assert "error" in await response.json()
        finally:
            await client.close()

    run(check())


def test_onboarding_supports_gas_kwh_but_rejects_bonus_and_wrong_unit():
    import pytest
    from radarcore.model import validate_settings

    with pytest.raises(ValueError):
        create_settings({"energy_type": "gas", "bonus": 100})
    with pytest.raises(ValueError):
        validate_settings(create_settings({"energy_type": "electricity", "source_unit": "m³"}))
    assert validate_settings(create_settings({"energy_type": "gas", "source_unit": "kWh"}))["source_unit"] == "kWh"
    assert create_settings({"energy_type": "gas"})["source_unit"] == "m³"
    assert create_settings({"energy_type": "electricity"})["source_unit"] == "kWh"


def test_shared_model_and_ocr_are_identical():
    root = APP.parent / "custom_components" / "abschlagsradar"
    for name in ("model.py", "ocr_core.py"):
        assert (root / name).read_bytes() == (APP / "radarcore" / name).read_bytes()


def test_one_app_installs_bridge_and_keeps_user_configuration(tmp_path):
    from bridge_installer import ensure_bridge

    config = tmp_path / "ha"
    data = tmp_path / "data"
    config.mkdir()
    (config / "configuration.yaml").write_text("my existing settings\n")
    data.mkdir()
    private = config / "configuration.yaml"
    assert ensure_bridge(APP / "bridge", config, data) is True
    assert private.read_text() == "my existing settings\n"
    assert (config / "custom_components/abschlagsradar/manifest.json").exists()
    assert (data / "bridge-restart-needed").exists()
    assert ensure_bridge(APP / "bridge", config, data) is False
    target = config / "custom_components/abschlagsradar/const.py"
    target.write_text("old version")
    assert ensure_bridge(APP / "bridge", config, data) is True
    assert list((data / "bridge-backups").iterdir())
    assert private.read_text() == "my existing settings\n"


def test_bridge_installer_refuses_other_integration_and_symlinks(tmp_path):
    import pytest
    from bridge_installer import ensure_bridge

    config = tmp_path / "ha"
    data = tmp_path / "data"
    data.mkdir()
    target = config / "custom_components/abschlagsradar"
    target.mkdir(parents=True)
    (config / "configuration.yaml").write_text("existing config")
    (target / "manifest.json").write_text('{"domain":"another_integration"}')
    with pytest.raises(ValueError):
        ensure_bridge(APP / "bridge", config, data)
    assert not (target / "const.py").exists()
    config2 = tmp_path / "ha2"
    config2.mkdir()
    (config2 / "configuration.yaml").write_text("existing config")
    (config2 / "custom_components").symlink_to(config / "custom_components", target_is_directory=True)
    with pytest.raises(ValueError):
        ensure_bridge(APP / "bridge", config2, data)


def test_bundled_bridge_matches_release_sources():
    root = APP.parent / "custom_components/abschlagsradar"
    for p in root.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            assert p.read_bytes() == (APP / "bridge" / p.relative_to(root)).read_bytes()


def test_upgrade_removes_obsolete_code_and_retains_backup(tmp_path):
    from bridge_installer import ensure_bridge

    config, data = tmp_path / "ha", tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "configuration.yaml").write_text("existing settings")
    assert ensure_bridge(APP / "bridge", config, data)
    obsolete = config / "custom_components/abschlagsradar/obsolete.py"
    obsolete.write_text("unused old implementation")
    assert ensure_bridge(APP / "bridge", config, data)
    assert not obsolete.exists()
    assert any((backup / "obsolete.py").exists() for backup in (data / "bridge-backups").iterdir())


def test_bridge_preflight_refuses_nested_symlink_without_partial_update(tmp_path):
    import pytest
    from bridge_installer import ensure_bridge

    config, data = tmp_path / "ha", tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "configuration.yaml").write_text("existing settings")
    ensure_bridge(APP / "bridge", config, data)
    target = config / "custom_components/abschlagsradar"
    before = (target / "const.py").read_bytes()
    (target / "unsafe").symlink_to(tmp_path / "other", target_is_directory=True)
    with pytest.raises(ValueError, match="linked"):
        ensure_bridge(APP / "bridge", config, data)
    assert (target / "const.py").read_bytes() == before


def test_bridge_restores_previous_directory_if_atomic_publish_fails(tmp_path, monkeypatch):
    import pytest
    from bridge_installer import ensure_bridge

    config, data = tmp_path / "ha", tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "configuration.yaml").write_text("existing settings")
    ensure_bridge(APP / "bridge", config, data)
    target = config / "custom_components/abschlagsradar"
    (target / "old.py").write_text("previous revision")
    original = Path.replace

    def fail_stage(path, destination):
        if path.name.startswith(".abschlagsradar-stage-"):
            raise OSError("simulated rename failure")
        return original(path, destination)

    monkeypatch.setattr(Path, "replace", fail_stage)
    with pytest.raises(OSError, match="simulated"):
        ensure_bridge(APP / "bridge", config, data)
    assert (target / "old.py").read_text() == "previous revision"
    assert not list(target.parent.glob(".abschlagsradar-stage-*"))


def test_bridge_crash_after_publish_still_requires_manual_restart(tmp_path):
    import shutil

    from bridge_installer import ensure_bridge

    config, data = tmp_path / "ha", tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "configuration.yaml").write_text("existing settings")
    ensure_bridge(APP / "bridge", config, data)
    target = config / "custom_components/abschlagsradar"
    shutil.copytree(target, target.parent / ".abschlagsradar-previous")
    (data / "bridge-restart-needed").unlink()
    assert not ensure_bridge(APP / "bridge", config, data)
    assert (data / "bridge-restart-needed").exists()


def test_startup_never_follows_app_data_symlinks(tmp_path):
    import pytest
    from bridge_installer import ensure_bridge

    config, data = tmp_path / "ha", tmp_path / "data"
    config.mkdir()
    data.mkdir()
    (config / "configuration.yaml").write_text("user configuration")
    victim = tmp_path / "private-settings"
    victim.write_text("must remain intact")
    for name in ("bridge-restart-needed", "bridge-backups"):
        link = data / name
        link.symlink_to(victim)
        with pytest.raises(ValueError, match="linked App data"):
            ensure_bridge(APP / "bridge", config, data)
        assert victim.read_text() == "must remain intact"
        assert not (config / "custom_components").exists()
        link.unlink()


def test_backup_keeps_automatic_samples_and_manual_priority():
    from backup import read_backup
    from radarcore.model import validate_settings

    settings = validate_settings(create_settings({"energy_type": "gas"}))
    restored = read_backup(
        {
            "format": "abschlagsradar-backup",
            "version": 1,
            "contracts": [
                {
                    "settings": settings,
                    "history": {"readings": [{"date": "2025-01-02", "value": 120}]},
                    "automatic_readings": [{"date": "2025-01-01", "value": 100}, {"date": "2025-01-02", "value": 110}],
                }
            ],
        }
    )
    assert restored[0]["history"]["readings"] == [
        {"date": "2025-01-01", "value": 100},
        {"date": "2025-01-02", "value": 120},
    ]


def test_backup_rejects_bonus_and_wrong_versions():
    import pytest
    from backup import read_backup

    for data in (
        {},
        {"format": "abschlagsradar-backup", "version": 2, "contracts": []},
        {"format": "abschlagsradar-backup", "version": 1, "contracts": [{"settings": {"bonus": 100}}]},
    ):
        with pytest.raises(ValueError):
            read_backup(data)


class RestoreHA(FakeHA):
    """Model HA setup/reload independently of the HTTP restore implementation."""

    def __init__(self, rows=None, fail_restore=None):
        super().__init__()
        self.rows = rows or []
        self.fail_restore = fail_restore
        self.created = 0
        self.restores = 0
        self.loading = False

    async def call(self, msg):
        if msg["type"] == "abschlagsradar/app":
            if self.loading:
                self.loading = False
                raise ValueError("Unknown command while first entry loads")
            if not self.rows:
                raise ValueError("Unknown command on empty installation")
            return self.rows
        if msg["type"] == "abschlagsradar/restore":
            self.restores += 1
            if self.restores == self.fail_restore:
                raise ValueError("Simulated restore failure")
            row = next(row for row in self.rows if row["id"] == msg["entry_id"])
            row.update(msg["payload"])
            return {"restored": True}
        return await super().call(msg)

    async def rest(self, path, data=None, method=None):
        self.messages.append({"path": path, "data": data, "method": method})
        if method == "DELETE":
            self.rows = [row for row in self.rows if path != "config/config_entries/entry/" + row["id"]]
            return {}
        if path == "config/config_entries/entry":
            return [{"domain": "abschlagsradar", "entry_id": row["id"]} for row in self.rows]
        if path == "config/config_entries/flow":
            return {"flow_id": "restore", "type": "menu"}
        if "next_step_id" in data:
            self.energy = data["next_step_id"]
            return {
                "type": "form",
                "data_schema": [{"name": key} for key in create_settings({"energy_type": self.energy})],
            }
        self.created += 1
        entry_id = "new-" + str(self.created)
        self.rows.append({"id": entry_id, "settings": data, "history": {"readings": []}})
        self.loading = self.created == 1
        return {"type": "create_entry", "result": {"entry_id": entry_id}}


def restore_backup():
    return {
        "format": "abschlagsradar-backup",
        "version": 1,
        "contracts": [
            {
                "settings": create_settings({"energy_type": energy, "billing_start": "2026-01-01"}),
                "history": {"readings": [{"date": "2026-01-01", "value": 100}, {"date": "2026-02-01", "value": 120}]},
                "automatic_readings": [{"date": "2026-03-01", "value": 150}],
            }
            for energy in ("electricity", "gas")
        ],
    }


def test_restore_creates_all_contracts_in_empty_app(tmp_path):
    async def check():
        from backup import read_backup

        ha = RestoreHA()
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            backup = restore_backup()
            response = await client.post(
                "/api/restore",
                json={"mode": "create", "contract_indices": [0, 1], "backup": backup},
                headers={"X-Remote-User-Id": "admin"},
            )
            assert response.status == 200, await response.text()
            result = await response.json()
            assert result["created"] == ["new-1", "new-2"] and result["count"] == 2
            expected = read_backup(backup)
            assert [row["history"] for row in ha.rows] == [row["history"] for row in expected]
            assert [row["settings"] for row in ha.rows] == [row["settings"] for row in expected]
        finally:
            await client.close()

    run(check())


def test_restore_rolls_back_new_contracts_without_touching_existing(tmp_path):
    async def check():
        original = {"id": "existing", "settings": create_settings({"energy_type": "gas"}), "history": {"readings": []}}
        ha = RestoreHA([original.copy()], fail_restore=2)
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            response = await client.post(
                "/api/restore",
                json={"mode": "create", "contract_indices": [0, 1], "backup": restore_backup()},
                headers={"X-Remote-User-Id": "admin"},
            )
            assert response.status == 400
            assert ha.rows == [original]
            removed = [msg["path"] for msg in ha.messages if msg.get("method") == "DELETE"]
            assert removed == ["config/config_entries/entry/new-2", "config/config_entries/entry/new-1"]
        finally:
            await client.close()

    run(check())


def test_restore_replace_keeps_identity_and_rejects_mismatch(tmp_path):
    async def check():
        row = {"id": "existing", "settings": create_settings({"energy_type": "gas"}), "history": {"readings": []}}
        ha = RestoreHA([row])
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            payload = {"entry_id": "existing", "contract_index": 0, "backup": restore_backup()}
            response = await client.post("/api/restore", json=payload, headers={"X-Remote-User-Id": "admin"})
            assert response.status == 400 and ha.restores == 0
            payload["contract_index"] = 1
            response = await client.post("/api/restore", json=payload, headers={"X-Remote-User-Id": "admin"})
            assert response.status == 200
            assert len(ha.rows) == 1 and ha.rows[0]["id"] == "existing" and ha.created == 0
        finally:
            await client.close()

    run(check())


def test_restore_validates_selection_and_admin_before_writes(tmp_path):
    async def check():
        ha = RestoreHA()
        client = TestClient(TestServer(create_app(ha, SnapshotStore(tmp_path / "s.db"), {"127.0.0.1"})))
        await client.start_server()
        try:
            payload = {"mode": "create", "contract_indices": [0, 1], "backup": restore_backup()}
            response = await client.post("/api/restore", json=payload, headers={"X-Remote-User-Id": "reader"})
            assert response.status == 403
            for selection in ([], [True], [0, 0], [2], "all"):
                payload["contract_indices"] = selection
                response = await client.post("/api/restore", json=payload, headers={"X-Remote-User-Id": "admin"})
                assert response.status == 400
            assert ha.created == 0
        finally:
            await client.close()

    run(check())
