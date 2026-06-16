#!/usr/bin/env python3
"""
Storage backend data migration script

Usage:
  python scripts/migrate_storage.py --from json --to postgres
  python scripts/migrate_storage.py --from json --to postgres --dry-run
  python scripts/migrate_storage.py --from json --to postgres --backup-dir data/backups/pre-postgres
  python scripts/migrate_storage.py --from json --to postgres --verify-only
  python scripts/migrate_storage.py --from sqlite --to postgres
  python scripts/migrate_storage.py --export data/backups/postgres-full.json
  python scripts/migrate_storage.py --import data/backups/postgres-full.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

from services.repositories.base import RepositoryValidationError
from services.storage.factory import create_storage_backend
from scripts.storage_safety import (
    DATASET_SPECS,
    DatasetSpec,
    audit_data_dir,
    create_backup,
    format_audit_report,
    format_backup_manifest,
    format_backup_verification,
    verify_backup,
)


EXTRA_DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec("quota_reservations", "quota_reservations.json", "id", "Quota reservations", unique_keys=("request_id",)),
    DatasetSpec("system_settings", "system_settings.json", "key", "System settings"),
    DatasetSpec("system_logs", "logs.jsonl", "id", "System logs"),
    DatasetSpec("audit_logs", "audit_logs.json", "id", "Audit logs"),
)
MIGRATION_DATASET_SPECS: tuple[DatasetSpec, ...] = DATASET_SPECS + EXTRA_DATASET_SPECS

DATASET_ACCESSORS = {
    "accounts": ("load_accounts", "save_accounts"),
    "auth_keys": ("load_auth_keys", "save_auth_keys"),
    "users": ("load_users", "save_users"),
    "sessions": ("load_sessions", "save_sessions"),
    "redeem_codes": ("load_redeem_codes", "save_redeem_codes"),
    "channels": ("load_channels", "save_channels"),
    "prompt_library": ("load_prompt_library", "save_prompt_library"),
    "image_records": ("load_image_records", "save_image_records"),
}


def export_to_json(output_file: str, *, dry_run: bool = False):
    """Export the full data of the current storage backend to a JSON file"""
    print(f"[migrate] Exporting data to {output_file}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    storage = create_storage_backend(DATA_DIR)
    try:
        data = _load_all_datasets(storage)
    finally:
        _close_storage(storage)
    _print_dataset_counts("Loaded for export", data)

    if dry_run:
        print(f"[migrate] Dry run: would export full dataset backup to {output_file}")
        return

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "datasets": data,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[migrate] Exported full dataset backup to {output_file}")


def import_from_json(
    input_file: str,
    *,
    dry_run: bool = False,
    backup_dir: str | None = None,
    verify_only: bool = False,
):
    """Import data from a JSON file into the current storage backend"""
    print(f"[migrate] Importing data from {input_file}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"[migrate] Error: File not found: {input_file}")
        sys.exit(1)
    
    try:
        data = _parse_import_payload(json.loads(input_path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        print(f"[migrate] Error: Invalid JSON: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[migrate] Error: {e}")
        sys.exit(1)

    _print_dataset_counts("Loaded from import file", data)
    if not _validate_dataset_report(data):
        sys.exit(1)

    if verify_only:
        print(f"[migrate] Verify only: {input_file} is a valid full dataset backup")
        return

    if dry_run:
        print(f"[migrate] Dry run: would import full dataset backup from {input_file}")
        return

    if backup_dir:
        _create_and_verify_backup(backup_dir)

    storage = create_storage_backend(DATA_DIR)
    try:
        try:
            _save_all_datasets(storage, data)
        except RepositoryValidationError as exc:
            print(f"[migrate] Error: {exc}")
            sys.exit(1)
        target_data = _load_all_datasets(storage)
        if not _verify_dataset_data(data, target_data):
            print("[migrate] Error: import verification failed")
            sys.exit(1)
    finally:
        _close_storage(storage)

    print("[migrate] Imported full dataset backup")


def migrate_data(
    from_backend: str,
    to_backend: str,
    *,
    dry_run: bool = False,
    backup_dir: str | None = None,
    verify_only: bool = False,
):
    """Migrate from one storage backend to another"""
    print(f"[migrate] Migrating from {from_backend} to {to_backend}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Save the original environment variable
    original_backend = os.environ.get("STORAGE_BACKEND")
    from_storage = None
    to_storage = None

    try:
        # Read data from the source backend
        os.environ["STORAGE_BACKEND"] = from_backend
        from_storage = create_storage_backend(DATA_DIR)
        source_data = _load_all_datasets(from_storage)
        _print_dataset_counts(f"Loaded from {from_backend}", source_data)
        if not _validate_dataset_report(source_data):
            sys.exit(1)

        if verify_only:
            os.environ["STORAGE_BACKEND"] = to_backend
            to_storage = create_storage_backend(DATA_DIR)
            target_data = _load_all_datasets(to_storage)
            _print_dataset_counts(f"Loaded from {to_backend}", target_data)
            if not _verify_dataset_data(source_data, target_data):
                sys.exit(1)
            print("[migrate] Verification completed successfully!")
            return

        if dry_run:
            _print_dataset_counts(f"Dry run: would save to {to_backend}", source_data)
            print("[migrate] Dry run completed without writing data.")
            return

        if backup_dir:
            _create_and_verify_backup(backup_dir)
        
        # Write to the target backend
        os.environ["STORAGE_BACKEND"] = to_backend
        to_storage = create_storage_backend(DATA_DIR)
        try:
            _save_all_datasets(to_storage, source_data)
        except RepositoryValidationError as exc:
            print(f"[migrate] Error: {exc}")
            sys.exit(1)
        _print_dataset_counts(f"Saved to {to_backend}", source_data)

        target_data = _load_all_datasets(to_storage)
        if not _verify_dataset_data(source_data, target_data):
            print("[migrate] Error: post-migration verification failed")
            sys.exit(1)
        
        print(f"[migrate] Migration completed successfully!")
        
    finally:
        _close_storage(to_storage)
        _close_storage(from_storage)
        # Restore the original environment variable
        if original_backend:
            os.environ["STORAGE_BACKEND"] = original_backend
        elif "STORAGE_BACKEND" in os.environ:
            del os.environ["STORAGE_BACKEND"]


def verify_backup_dir(backup_dir: str) -> None:
    report = verify_backup(Path(backup_dir))
    print(format_backup_verification(report))
    if report["status"] != "ok":
        sys.exit(1)


def audit_json_data(*, fail_on_issues: bool = False) -> None:
    report = audit_data_dir(DATA_DIR)
    print(format_audit_report(report))
    if fail_on_issues and int(report["summary"]["problem_count"]) > 0:
        sys.exit(1)


def _load_all_datasets(storage) -> dict[str, list[dict]]:
    data = {}
    for spec in DATASET_SPECS:
        loader_name, _ = DATASET_ACCESSORS[spec.name]
        data[spec.name] = list(getattr(storage, loader_name)())
    provider = _repository_provider(storage)
    if provider is not None:
        data["quota_reservations"] = list(provider.quota_reservations.list())
        data["system_settings"] = _settings_to_items(provider.system_config.list_settings())
        data["system_logs"] = list(provider.system_logs.list())
        data["audit_logs"] = list(provider.audit_logs.list())
        return data

    data["quota_reservations"] = []
    data["system_settings"] = []
    if _backend_type(storage) == "json":
        system_logs = _load_jsonl_logs(DATA_DIR / "logs.jsonl")
        data["system_logs"] = system_logs
        data["audit_logs"] = _audit_logs_from_system_logs(system_logs)
    else:
        data["system_logs"] = []
        data["audit_logs"] = []
    return data


def _save_all_datasets(storage, data: dict[str, list[dict]]) -> None:
    for spec in DATASET_SPECS:
        _, saver_name = DATASET_ACCESSORS[spec.name]
        getattr(storage, saver_name)(data.get(spec.name, []))
    provider = _repository_provider(storage)
    if provider is not None:
        _replace_repository_items(provider.quota_reservations, data.get("quota_reservations", []), "quota_reservations")
        _replace_system_settings(provider.system_config, data.get("system_settings", []))
        _replace_repository_items(provider.system_logs, data.get("system_logs", []), "system_logs")
        _replace_repository_items(provider.audit_logs, data.get("audit_logs", []), "audit_logs")
    elif _backend_type(storage) == "json":
        _save_jsonl_logs(DATA_DIR / "logs.jsonl", data.get("system_logs", []), data.get("audit_logs", []))


def _parse_import_payload(payload: object) -> dict[str, list[dict]]:
    if isinstance(payload, list):
        return {
            spec.name: payload if spec.name == "accounts" else []
            for spec in MIGRATION_DATASET_SPECS
        }
    if not isinstance(payload, dict):
        raise ValueError("Invalid JSON format, expected full export object or legacy accounts array")

    raw_datasets = payload.get("datasets")
    if raw_datasets is None:
        raw_datasets = payload
    if not isinstance(raw_datasets, dict):
        raise ValueError("Invalid JSON format, field 'datasets' must be an object")

    data: dict[str, list[dict]] = {}
    for spec in MIGRATION_DATASET_SPECS:
        items = raw_datasets.get(spec.name, [])
        if spec.list_key and isinstance(items, dict):
            items = items.get(spec.list_key, [])
        if not isinstance(items, list):
            raise ValueError(f"Invalid JSON format, dataset {spec.name!r} must be an array")
        data[spec.name] = items
    return data


def _validate_dataset_report(data: dict[str, list[dict]]) -> bool:
    ok = True
    for spec in MIGRATION_DATASET_SPECS:
        items = data.get(spec.name, [])
        problems = _dataset_problems(items, spec.primary_key, spec.unique_keys)
        if problems:
            ok = False
            print(f"[migrate] Validation failed for {spec.name}:")
            for problem in problems[:20]:
                print(f"[migrate]   - {problem}")
            if len(problems) > 20:
                print(f"[migrate]   - ... {len(problems) - 20} more")
    return ok


def _dataset_problems(items: list[dict], primary_key: str, unique_keys: tuple[str, ...]) -> list[str]:
    problems: list[str] = []
    primary_seen: dict[str, int] = {}
    unique_seen: dict[str, dict[str, int]] = {key: {} for key in unique_keys}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"index {index}: item is not an object")
            continue
        primary_value = _clean_value(item.get(primary_key))
        if not primary_value:
            problems.append(f"index {index}: missing primary key {primary_key!r}")
        elif primary_value in primary_seen:
            problems.append(
                f"index {index}: duplicate primary key {primary_key!r} "
                f"(first index {primary_seen[primary_value]}, value_sha256={_sha_preview(primary_value)})"
            )
        else:
            primary_seen[primary_value] = index
        for unique_key in unique_keys:
            value = _clean_value(item.get(unique_key))
            if not value:
                continue
            seen = unique_seen[unique_key]
            if value in seen:
                problems.append(
                    f"index {index}: duplicate unique key {unique_key!r} "
                    f"(first index {seen[value]}, value_sha256={_sha_preview(value)})"
                )
            else:
                seen[value] = index
    return problems


def _verify_dataset_data(source: dict[str, list[dict]], target: dict[str, list[dict]]) -> bool:
    ok = True
    for spec in MIGRATION_DATASET_SPECS:
        source_items = source.get(spec.name, [])
        target_items = target.get(spec.name, [])
        if len(source_items) != len(target_items):
            print(
                f"[migrate] Verify failed for {spec.name}: "
                f"source count={len(source_items)}, target count={len(target_items)}"
            )
            ok = False
            continue
        source_keys = _key_set(source_items, spec.primary_key)
        target_keys = _key_set(target_items, spec.primary_key)
        if source_keys != target_keys:
            print(f"[migrate] Verify failed for {spec.name}: primary key set mismatch")
            ok = False
    return ok


def _key_set(items: list[dict], key: str) -> set[str]:
    return {
        str(item.get(key) or "").strip()
        for item in items
        if isinstance(item, dict) and str(item.get(key) or "").strip()
    }


def _clean_value(value: object) -> str:
    return str(value or "").strip()


def _sha_preview(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _print_dataset_counts(label: str, data: dict[str, list[dict]]) -> None:
    counts = ", ".join(f"{spec.name}={len(data.get(spec.name, []))}" for spec in MIGRATION_DATASET_SPECS)
    print(f"[migrate] {label}: {counts}")


def _repository_provider(storage):
    provider = getattr(storage, "repository_provider", None)
    return provider


def _backend_type(storage) -> str:
    try:
        info = storage.get_backend_info()
    except Exception:
        return ""
    return str(info.get("type") or info.get("backend") or "").strip().lower()


def _settings_to_items(settings: dict[str, object]) -> list[dict]:
    return [
        {"key": str(key), "value": value}
        for key, value in sorted((settings or {}).items(), key=lambda pair: str(pair[0]))
    ]


def _settings_from_items(items: list[dict]) -> dict[str, object]:
    settings: dict[str, object] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _clean_value(item.get("key") or item.get("setting_key"))
        if key:
            settings[key] = item.get("value")
    return settings


def _replace_system_settings(repository, items: list[dict]) -> None:
    settings = _settings_from_items(items)
    for key in list(repository.list_settings()):
        if key not in settings:
            repository.delete_setting(key)
    for key, value in settings.items():
        repository.set_setting(key, value)


def _replace_repository_items(repository, items: list[dict], dataset_name: str) -> None:
    replace_all = getattr(repository, "replace_all", None)
    if not callable(replace_all):
        if items:
            raise RuntimeError(f"{dataset_name} cannot be imported by this storage backend")
        return
    replace_all(items)


def _load_jsonl_logs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    logs: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"[migrate] Skipping invalid logs.jsonl line {line_number}: {exc}")
            continue
        if isinstance(item, dict):
            if not _clean_value(item.get("id") or item.get("log_id")):
                item = dict(item)
                item["id"] = _stable_file_log_id(item, line_number)
            logs.append(item)
    return logs


def _save_jsonl_logs(path: Path, system_logs: list[dict], audit_logs: list[dict]) -> None:
    logs = system_logs if system_logs else audit_logs
    if not logs:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in logs),
        encoding="utf-8",
    )


def _audit_logs_from_system_logs(system_logs: list[dict]) -> list[dict]:
    audit_logs: list[dict] = []
    seen: set[str] = set()
    for log in system_logs:
        if not isinstance(log, dict) or _clean_value(log.get("type")) != "audit":
            continue
        detail = log.get("detail")
        if isinstance(detail, dict) and (
            detail.get("action") or detail.get("actor_id") or detail.get("resource") or detail.get("target_id")
        ):
            item = dict(detail)
        else:
            item = dict(log)
        item["id"] = _clean_value(item.get("id") or item.get("audit_id") or log.get("id") or log.get("log_id"))
        if not item["id"]:
            continue
        if item["id"] in seen:
            continue
        seen.add(str(item["id"]))
        item.setdefault("audit_id", item["id"])
        item.setdefault("time", log.get("time") or "")
        item.setdefault("request_id", log.get("request_id") or "")
        item.setdefault("type", "audit")
        if not _clean_value(item.get("action")):
            item["action"] = _clean_value(log.get("summary"))
        item.setdefault("summary", item.get("action") or log.get("summary") or "")
        audit_logs.append(item)
    return audit_logs


def _stable_file_log_id(item: dict, line_number: int) -> str:
    import hashlib

    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{line_number}:{payload}".encode("utf-8")).hexdigest()[:24]
    return f"file-log-{digest}"


def _create_and_verify_backup(backup_dir: str) -> None:
    manifest = create_backup(DATA_DIR, Path(backup_dir))
    print(format_backup_manifest(manifest))
    report = verify_backup(Path(backup_dir))
    print(format_backup_verification(report))
    if report["status"] != "ok":
        print("[migrate] Error: backup verification failed; migration aborted")
        sys.exit(1)


def _close_storage(storage) -> None:
    if storage is None:
        return
    close = getattr(storage, "close", None)
    if callable(close):
        close()


def main():
    parser = argparse.ArgumentParser(
        description="ChatGPT2API storage backend data migration tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate from JSON to PostgreSQL
  python scripts/migrate_storage.py --from json --to postgres

  # Dry run before migrating, without writing to the target backend
  python scripts/migrate_storage.py --from json --to postgres --dry-run

  # Create and verify a full JSON backup before migrating
  python scripts/migrate_storage.py --from json --to postgres --backup-dir data/backups/pre-postgres

  # Only verify the item counts and primary key sets of both backends
  python scripts/migrate_storage.py --from json --to postgres --verify-only

  # Export the full data of the current backend to a JSON file
  python scripts/migrate_storage.py --export backup.json

  # Import data from a full JSON backup
  python scripts/migrate_storage.py --import backup.json

Environment variables:
  STORAGE_BACKEND  - Storage backend type (json, sqlite, postgres, git, d1)
  DATABASE_URL     - Database connection string
  GIT_REPO_URL     - Git repository URL
  GIT_TOKEN        - Git access token
        """
    )
    
    parser.add_argument(
        "--from",
        dest="from_backend",
        choices=["json", "sqlite", "postgres", "git", "d1"],
        help="Source storage backend",
    )
    parser.add_argument(
        "--to",
        dest="to_backend",
        choices=["json", "sqlite", "postgres", "git", "d1"],
        help="Target storage backend",
    )
    parser.add_argument(
        "--export",
        dest="export_file",
        metavar="FILE",
        help="Export data to a JSON file",
    )
    parser.add_argument(
        "--import",
        dest="import_file",
        metavar="FILE",
        help="Import data from a JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run the migration/import/export without writing any data",
    )
    parser.add_argument(
        "--backup-dir",
        help="Create and verify a full JSON backup directory before writing; when used alone with --verify-only, verify that backup directory",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run verification; do not migrate, import, or export",
    )
    
    args = parser.parse_args()
    
    # Check arguments
    if args.from_backend and args.to_backend:
        migrate_data(
            args.from_backend,
            args.to_backend,
            dry_run=args.dry_run,
            backup_dir=args.backup_dir,
            verify_only=args.verify_only,
        )
    elif args.export_file:
        if args.verify_only:
            print("[migrate] Error: --verify-only cannot be used with --export")
            sys.exit(1)
        export_to_json(args.export_file, dry_run=args.dry_run)
    elif args.import_file:
        import_from_json(
            args.import_file,
            dry_run=args.dry_run,
            backup_dir=args.backup_dir,
            verify_only=args.verify_only,
        )
    elif args.verify_only and args.backup_dir:
        verify_backup_dir(args.backup_dir)
    elif args.verify_only:
        audit_json_data(fail_on_issues=True)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
