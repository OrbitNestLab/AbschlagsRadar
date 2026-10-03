"""Export only tracked/reviewed source files, with optional fresh project history.

Never copies existing Git metadata, personal development history or local backups.
The export remains local; no remote, upload or publication is created.
"""

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".venv"}


def export(destination, fresh_git=False):
    destination = Path(destination).resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError("Export outside the development source folder")
    if destination.exists():
        raise ValueError("Destination must not already exist")
    listed = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    # New release files must be deliberately staged before they are eligible.
    files = [ROOT / os.fsdecode(name) for name in listed if name]
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED for part in relative.parts) or path.is_symlink() or not path.is_file():
            raise ValueError("Unexpected source file: " + str(relative))
        data = path.read_bytes()
        if re.search(
            rb"/Users/[A-Za-z0-9_.-]+/|192\.168\.\d+\.\d+|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", data
        ):
            raise ValueError("Private source content: " + str(relative))
    destination.mkdir(parents=True)
    for path in files:
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    if fresh_git:
        subprocess.run(["git", "init", "--initial-branch=main", str(destination)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AbschlagsRadar"], cwd=destination, check=True)
        # Reserved .invalid domain: does not expose or impersonate a real mailbox.
        subprocess.run(
            ["git", "config", "user.email", "maintainers@abschlagsradar.invalid"], cwd=destination, check=True
        )
        subprocess.run(["git", "add", "."], cwd=destination, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "Prepare AbschlagsRadar source"],
            cwd=destination,
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "AbschlagsRadar",
                "GIT_AUTHOR_EMAIL": "maintainers@abschlagsradar.invalid",
                "GIT_COMMITTER_NAME": "AbschlagsRadar",
                "GIT_COMMITTER_EMAIL": "maintainers@abschlagsradar.invalid",
            },
        )
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    parser.add_argument("--fresh-git", action="store_true")
    args = parser.parse_args()
    print(f"Prepared {export(args.destination, args.fresh_git)} source files locally. Nothing uploaded.")


if __name__ == "__main__":
    main()
