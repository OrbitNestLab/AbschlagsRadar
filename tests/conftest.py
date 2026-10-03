"""Load pure modules without importing Home Assistant's integration entrypoint."""

import importlib.util
import sys
import types
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "custom_components" / "abschlagsradar"
package = types.ModuleType("budget_under_test")
package.__path__ = [str(BASE)]
sys.modules["budget_under_test"] = package
for name in ("model", "ocr_core"):
    spec = importlib.util.spec_from_file_location(f"budget_under_test.{name}", BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
