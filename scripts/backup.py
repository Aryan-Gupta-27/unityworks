"""Copy or restore the UnityWorks database and uploads.

Does not delete the live database. Restore refuses to overwrite an existing
destination database or uploads folder.
"""

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def backup(instance, dest):
    instance = Path(instance)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = Path(dest) / stamp
    target.mkdir(parents=True, exist_ok=False)
    db_path = instance / "unityworks.db"
    if db_path.exists():
        _copy_db(db_path, target / "unityworks.db")
    uploads = instance / "uploads"
    if uploads.exists():
        shutil.copytree(uploads, target / "uploads")
    return target


def restore(backup_dir, dest):
    backup_dir = Path(backup_dir)
    dest = Path(dest)
    db_path = backup_dir / "unityworks.db"
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    dest.mkdir(parents=True, exist_ok=True)
    dest_db = dest / "unityworks.db"
    if dest_db.exists():
        raise FileExistsError(f"Refusing to overwrite {dest_db}")
    _copy_db(db_path, dest_db)
    uploads = backup_dir / "uploads"
    dest_uploads = dest / "uploads"
    if uploads.exists():
        if dest_uploads.exists():
            raise FileExistsError(f"Refusing to overwrite {dest_uploads}")
        shutil.copytree(uploads, dest_uploads)
    return dest


def orphans(instance):
    """Stored files that no row points at. Does not delete anything."""
    instance = Path(instance)
    folder = instance / "uploads" / "files"
    if not folder.exists():
        return []
    referenced = set()
    db_path = instance / "unityworks.db"
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            for table, column in (("files", "stored_name"), ("academic_resources", "stored_name")):
                try:
                    rows = conn.execute(f"SELECT {column} FROM {table}").fetchall()
                except sqlite3.OperationalError:
                    continue
                referenced.update(row[0] for row in rows if row[0])
        finally:
            conn.close()
    return sorted(path.name for path in folder.iterdir() if path.is_file() and path.name not in referenced)


def _copy_db(source, dest):
    src = sqlite3.connect(source)
    dst = sqlite3.connect(dest)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()


def main():
    parser = argparse.ArgumentParser(description="Back up or restore UnityWorks data.")
    parser.add_argument("action", choices=["backup", "restore", "orphans"])
    parser.add_argument("--instance", default="instance")
    parser.add_argument("--dest", default="backups")
    parser.add_argument("--from", dest="source", help="Backup directory to restore.")
    args = parser.parse_args()
    if args.action == "backup":
        print(backup(args.instance, args.dest))
    elif args.action == "orphans":
        names = orphans(args.instance)
        print("\n".join(names) if names else "No orphan files.")
    else:
        if not args.source:
            raise SystemExit("restore needs --from")
        print(restore(args.source, args.dest))


if __name__ == "__main__":
    main()
