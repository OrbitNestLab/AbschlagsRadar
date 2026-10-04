"""Static integration contract checks for packaging and translation completeness."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/abschlagsradar"


def test_manifest_and_packaging():
    manifest = json.loads((BASE / "manifest.json").read_text())
    assert manifest["domain"] == BASE.name
    assert manifest["config_flow"] is True
    assert manifest["dependencies"] == []  # Photo processing is isolated in the App.
    assert manifest["requirements"] == []
    assert not (ROOT / "hacs.json").exists()
    app = (ROOT / "abschlagsradar_app" / "config.yaml").read_text()
    assert "slug: abschlagsradar" in app
    assert "ingress: true" in app
    for name in ("__init__", "const", "config_flow", "coordinator", "model", "storage", "sensor", "ocr_core"):
        ast.parse((BASE / f"{name}.py").read_text())


def test_installation_never_restarts_home_assistant_automatically():
    server = (ROOT / "abschlagsradar_app" / "server.py").read_text()
    installer = (ROOT / "Installieren.command").read_text()
    assert "services/homeassistant/restart" not in server
    assert '"service":"restart"' not in installer.replace(" ", "")


def test_translations_cover_all_sensor_and_flow_keys():
    en = json.loads((BASE / "translations/en.json").read_text())
    de = json.loads((BASE / "translations/de.json").read_text())
    assert en == json.loads((BASE / "strings.json").read_text())
    for area in ("config", "options"):
        assert set(en[area]["step"]) == set(de[area]["step"])
        assert set(en[area]["error"]) == set(de[area]["error"])
    assert set(en["entity"]["sensor"]) == set(de["entity"]["sensor"])
    assert len(en["entity"]["sensor"]) == 24
