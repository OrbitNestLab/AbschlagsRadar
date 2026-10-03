"""Fill real public metadata locally; never creates or publishes a repository."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Actual GitHub OWNER/REPOSITORY")
    parser.add_argument("--maintainer", required=True, help="Actual maintainer GitHub handle")
    parser.add_argument("--write", action="store_true", help="Apply locally; omission only previews")
    args = parser.parse_args()
    handle = args.maintainer.removeprefix("@")
    github_name = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
    if not re.fullmatch(github_name, handle) or not re.fullmatch(
        github_name + r"/[A-Za-z0-9_.-]{1,100}", args.repository
    ):
        parser.error("Supply a valid GitHub repository and maintainer handle.")
    url = "https://github.com/" + args.repository
    repository_path = ROOT / "repository.yaml"
    repository = yaml.safe_load(repository_path.read_text())
    repository.update(url=url, maintainer="@" + handle)
    app_path = ROOT / "abschlagsradar_app/config.yaml"
    app = yaml.safe_load(app_path.read_text())
    app["url"] = url
    manifest_path = ROOT / "custom_components/abschlagsradar/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(codeowners=["@" + handle], documentation=url, issue_tracker=url + "/issues")
    print("Repository:", url, "Maintainer: @" + handle)
    if not args.write:
        print("Preview only. Add --write to update local metadata and the packaged bridge.")
        return
    repository_path.write_text(yaml.safe_dump(repository, sort_keys=False, allow_unicode=True))
    app_path.write_text(yaml.safe_dump(app, sort_keys=False, allow_unicode=True))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    subprocess.run([sys.executable, str(ROOT / "tools/sync_sources.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/validate_release.py"), "--public"], check=True)
    print("Public metadata configured locally. Nothing has been uploaded or published.")


if __name__ == "__main__":
    main()
