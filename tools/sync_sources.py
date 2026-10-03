"""Keep packaged code identical to canonical sources; --check never writes."""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/abschlagsradar"
APP = ROOT / "abschlagsradar_app"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    failures = []
    canonical = {p.relative_to(SOURCE) for p in SOURCE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    for target in (APP / "bridge").rglob("*"):
        if (
            target.is_file()
            and "__pycache__" not in target.parts
            and target.relative_to(APP / "bridge") not in canonical
        ):
            if args.check:
                failures.append(str(target.relative_to(ROOT)))
            else:
                target.unlink()
    for source in sorted(SOURCE.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        destinations = [APP / "bridge" / source.relative_to(SOURCE)]
        if source.name in {"model.py", "ocr_core.py"}:
            destinations.append(APP / "radarcore" / source.name)
        for target in destinations:
            if args.check:
                if not target.is_file() or source.read_bytes() != target.read_bytes():
                    failures.append(str(target.relative_to(ROOT)))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    if failures:
        raise SystemExit("Packaged source mismatch: " + ", ".join(failures))


if __name__ == "__main__":
    main()
