"""Check package consistency offline; --public additionally needs real metadata."""

import argparse
import ast
import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load((ROOT / "abschlagsradar_app/config.yaml").read_text())
    version = config["version"]
    assert config["arch"] == ["amd64"], "Only validated architectures may be offered"
    assert config["ports"] == {} and config["ingress"] and not config["host_network"]
    assert tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] == version
    assert json.loads((ROOT / "package.json").read_text())["version"] == version
    assert (ROOT / "pnpm-lock.yaml").is_file(), "Missing pinned browser test dependencies"
    for prefix in ("custom_components/abschlagsradar", "abschlagsradar_app/bridge"):
        assert json.loads((ROOT / prefix / "manifest.json").read_text())["version"] == version
    assert f'VERSION = "{version}"' in (ROOT / "abschlagsradar_app/server.py").read_text()
    assert f"ARG BUILD_VERSION={version}" in (ROOT / "abschlagsradar_app/Dockerfile").read_text()
    assert (ROOT / "abschlagsradar_app/CHANGELOG.md").read_text().startswith(f"# {version}\n")
    for filename in ("README.md", "LICENSE", "DOCS.md", "CHANGELOG.md"):
        assert (ROOT / "abschlagsradar_app" / filename).is_file(), f"Missing App {filename}"
    for path in ROOT.rglob("*"):
        if any(
            part.startswith(".") or part in {"__pycache__", "node_modules"} for part in path.relative_to(ROOT).parts
        ):
            continue
        assert not path.is_symlink(), f"Unexpected linked release file: {path.name}"
        if path.suffix == ".json":
            json.loads(path.read_text())
        elif path.suffix == ".py":
            ast.parse(path.read_text())
    lock = (ROOT / "abschlagsradar_app/requirements-lock.txt").read_text().splitlines()
    assert lock and all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", line) for line in lock)
    if args.public:
        repository = yaml.safe_load((ROOT / "repository.yaml").read_text())
        assert repository.get("url", "").startswith("https://github.com/"), "Supply real repository URL"
        assert config.get("url") == repository["url"], "App URL must match repository"
        manifest = json.loads((ROOT / "custom_components/abschlagsradar/manifest.json").read_text())
        assert manifest["codeowners"], "Supply real maintainer GitHub handle"
        assert manifest.get("documentation", "").startswith(repository["url"])
    print(f"Release {version}: versions, files, syntax, local access and dependency pins consistent.")


if __name__ == "__main__":
    main()
