#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.storage_safety import audit_data_dir, format_audit_report


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only audit of YanAI legacy JSON storage data",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help="JSON data directory, defaults to ./data",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output a machine-readable JSON report",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Return a non-zero exit code when invalid JSON, missing primary keys, or duplicate primary keys are found",
    )
    args = parser.parse_args()

    report = audit_data_dir(Path(args.data_dir))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_audit_report(report))

    if args.fail_on_issues and int(report["summary"]["problem_count"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
