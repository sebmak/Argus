import sqlite3
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable

from ..config import settings

logger = logging.getLogger(__name__)

def parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """Parses semantic version string like '1.1.0' into (1, 1, 0) for ordering comparisons."""
    clean = re.sub(r"[^\d.]", "", str(version_str)).strip(".")
    if not clean:
        return (0, 0, 0)
    return tuple(int(part) for part in clean.split(".") if part.isdigit())

def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Checks whether a table exists in the SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None

def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """Checks whether a column exists in a given table."""
    if not table_exists(conn, table_name):
        return False
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    col_type: str,
    default: Optional[str] = None
) -> bool:
    """Safely adds a column to an existing table if it does not already exist."""
    if not column_exists(conn, table_name, column_name):
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type}{default_clause}")
        logger.info("Non-destructive migration: Added column '%s' to table '%s'", column_name, table_name)
        return True
    return False

def backup_database(db_path: str, reason: str = "backup", max_backups: int = 5) -> Optional[str]:
    """Creates a non-locking, atomic backup snapshot of the SQLite database."""
    p = Path(db_path)
    if not p.is_file():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = p.parent / f"{p.name}.{reason}_{timestamp}.bak"

    try:
        source_conn = sqlite3.connect(str(p))
        dest_conn = sqlite3.connect(str(backup_file))
        source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
        logger.info("Database backup created successfully: %s", backup_file)

        # Retain only the most recent backups
        backups = sorted(p.parent.glob(f"{p.name}.*_{reason}_*.bak") if reason else p.parent.glob(f"{p.name}.*.bak"))
        if len(backups) > max_backups:
            for old_bak in backups[:-max_backups]:
                try:
                    old_bak.unlink()
                except OSError:
                    pass

        return str(backup_file)
    except Exception as e:
        logger.warning("Database backup creation failed: %s", e)
        return None


# ==============================================================================
# Rules for MigrationStep:
# 1. Represents an individual, atomic, reversible schema migration unit.
# 2. Member variables must be declared at the top of the class.
# 3. 'up' and 'down' methods must execute safe, non-destructive SQL commands.
# 4. 'down' must preserve core household member and face embedding data.
# ==============================================================================
class MigrationStep:
    migration_id: int
    version_tag: str
    name: str
    description: str
    up_fn: Callable[[sqlite3.Connection], None]
    down_fn: Callable[[sqlite3.Connection], None]

    def __init__(
        self,
        migration_id: int,
        version_tag: str,
        name: str,
        description: str,
        up_fn: Callable[[sqlite3.Connection], None],
        down_fn: Callable[[sqlite3.Connection], None]
    ):
        self.migration_id = migration_id
        self.version_tag = version_tag
        self.name = name
        self.description = description
        self.up_fn = up_fn
        self.down_fn = down_fn

    def up(self, conn: sqlite3.Connection):
        self.up_fn(conn)

    def down(self, conn: sqlite3.Connection):
        self.down_fn(conn)


# ==============================================================================
# Rules for MigrationManager:
# 1. Orchestrates schema version tracking, roll-forward, and roll-back workflows.
# 2. Class and instance variables must be placed at the top of the class.
# 3. Automatic backups must be triggered before rollbacks or structural changes.
# 4. Must seamlessly inspect and backfill preexisting unversioned databases.
# ==============================================================================
class MigrationManager:
    migrations: List[MigrationStep] = []
    backup_retention: int = 5

    def __init__(self):
        self.migrations = []
        self._register_default_migrations()

    def register(self, step: MigrationStep):
        """Registers a migration step in chronological order."""
        self.migrations.append(step)
        self.migrations.sort(key=lambda m: m.migration_id)

    def _ensure_migration_table(self, conn: sqlite3.Connection):
        """Creates the schema_migrations tracking table if missing."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_id INTEGER UNIQUE NOT NULL,
                app_version TEXT NOT NULL,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _backfill_preexisting_db_if_needed(self, conn: sqlite3.Connection):
        """
        Detects if this is a pre-existing database created before schema_migrations
        existed, and safely registers existing migrations without breaking data.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_migrations")
        if cursor.fetchone()[0] == 0:
            # Check if core tables already exist
            if table_exists(conn, "persons") and table_exists(conn, "face_samples"):
                logger.info("Detected pre-existing database tables; backfilling migration 1 (v1.0.0)...")
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (migration_id, app_version, name) VALUES (?, ?, ?)",
                    (1, "1.0.0", "initial_household_schema")
                )
            if table_exists(conn, "settings"):
                logger.info("Detected pre-existing settings table; backfilling migration 2 (v1.1.0)...")
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (migration_id, app_version, name) VALUES (?, ?, ?)",
                    (2, "1.1.0", "dynamic_settings_and_telemetry")
                )
            conn.commit()

    def get_applied_migrations(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Returns list of applied migrations ordered by ID."""
        self._ensure_migration_table(conn)
        self._backfill_preexisting_db_if_needed(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT migration_id, app_version, name, applied_at FROM schema_migrations ORDER BY migration_id ASC")
        return [
            {
                "migration_id": row[0],
                "app_version": row[1],
                "name": row[2],
                "applied_at": row[3]
            }
            for row in cursor.fetchall()
        ]

    def get_current_app_version(self, conn: sqlite3.Connection) -> str:
        """Returns the highest app_version recorded in migrations, or 1.0.0."""
        applied = self.get_applied_migrations(conn)
        if not applied:
            return "1.0.0"
        return applied[-1]["app_version"]

    def migrate_to_app_version(
        self,
        target_app_version: str,
        db_path: str
    ) -> Dict[str, Any]:
        """
        Reconciles database schema with target application version.
        Rolls forward if database is behind target version.
        Rolls back safely if database is ahead of target version (server rollback).
        """
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        target_tuple = parse_version_tuple(target_app_version)
        backup_path = None
        applied_names = []
        rolled_back_names = []

        conn = sqlite3.connect(str(p), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        try:
            self._ensure_migration_table(conn)
            self._backfill_preexisting_db_if_needed(conn)

            applied_records = self.get_applied_migrations(conn)
            applied_ids = {rec["migration_id"] for rec in applied_records}

            # 1. Check if database is AHEAD of target app version -> ROLL BACK
            migrations_to_rollback = []
            for step in reversed(self.migrations):
                step_version_tuple = parse_version_tuple(step.version_tag)
                if step.migration_id in applied_ids and step_version_tuple > target_tuple:
                    migrations_to_rollback.append(step)

            if migrations_to_rollback:
                logger.warning(
                    "Server downgrade/rollback detected! Current database has migrations beyond app version %s. Executing safe rollbacks...",
                    target_app_version
                )
                backup_path = backup_database(db_path, reason="pre_rollback")
                for step in migrations_to_rollback:
                    logger.info("Rolling back migration %d: '%s' (%s)...", step.migration_id, step.name, step.version_tag)
                    step.down(conn)
                    conn.execute("DELETE FROM schema_migrations WHERE migration_id = ?", (step.migration_id,))
                    conn.commit()
                    rolled_back_names.append(step.name)

            # 2. Check if database is BEHIND target app version -> ROLL FORWARD
            # Re-read applied IDs after potential rollbacks
            applied_records = self.get_applied_migrations(conn)
            applied_ids = {rec["migration_id"] for rec in applied_records}

            migrations_to_apply = []
            for step in self.migrations:
                step_version_tuple = parse_version_tuple(step.version_tag)
                if step.migration_id not in applied_ids and step_version_tuple <= target_tuple:
                    migrations_to_apply.append(step)

            if migrations_to_apply:
                if not backup_path and p.is_file():
                    backup_path = backup_database(db_path, reason="pre_migration")

                for step in migrations_to_apply:
                    logger.info("Applying migration %d: '%s' (app version %s)...", step.migration_id, step.name, step.version_tag)
                    step.up(conn)
                    conn.execute(
                        "INSERT INTO schema_migrations (migration_id, app_version, name) VALUES (?, ?, ?)",
                        (step.migration_id, step.version_tag, step.name)
                    )
                    conn.commit()
                    applied_names.append(step.name)

            current_version = self.get_current_app_version(conn)
            return {
                "status": "success",
                "target_app_version": target_app_version,
                "current_app_version": current_version,
                "applied": applied_names,
                "rolled_back": rolled_back_names,
                "backup_path": backup_path
            }

        finally:
            conn.close()

    def _register_default_migrations(self):
        """Registers all built-in versioned migration steps."""

        # ----------------------------------------------------------------------
        # Migration 1 (v1.0.0): Core Household Face Detection & Recognition
        # ----------------------------------------------------------------------
        def up_v1_0_0(conn: sqlite3.Connection):
            cursor = conn.cursor()
            # Persons
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Face Samples (ArcFace 512-d embeddings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS face_samples (
                    id TEXT PRIMARY KEY,
                    person_id TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    thumbnail_path TEXT NOT NULL,
                    source TEXT DEFAULT 'manual',
                    camera_id TEXT DEFAULT '',
                    event_id TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_samples_person ON face_samples(person_id);")

            # Detections History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    camera_id TEXT DEFAULT '',
                    thumbnail_path TEXT NOT NULL,
                    bbox TEXT DEFAULT '[]',
                    matched_person_id TEXT,
                    matched_name TEXT,
                    similarity REAL DEFAULT 0.0,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (matched_person_id) REFERENCES persons(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_detections_status ON detections(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_detections_time ON detections(timestamp);")

            # Users (Dashboard Auth)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default admin user if none exists
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                admin_id = f"u_{uuid.uuid4().hex[:12]}"
                from .database import hash_password
                hashed_pw = hash_password(settings.DEFAULT_ADMIN_PASSWORD)
                cursor.execute(
                    "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
                    (admin_id, settings.DEFAULT_ADMIN_USER, hashed_pw)
                )

        def down_v1_0_0(conn: sqlite3.Connection):
            # Non-destructive: drop secondary indexes but preserve user data
            conn.execute("DROP INDEX IF EXISTS idx_samples_person;")
            conn.execute("DROP INDEX IF EXISTS idx_detections_status;")
            conn.execute("DROP INDEX IF EXISTS idx_detections_time;")

        self.register(MigrationStep(
            migration_id=1,
            version_tag="1.0.0",
            name="initial_household_schema",
            description="Initial schema with persons, face_samples, detections, and users.",
            up_fn=up_v1_0_0,
            down_fn=down_v1_0_0
        ))

        # ----------------------------------------------------------------------
        # Migration 2 (v1.1.0): Dynamic Settings, RTSP Stream & Telemetry
        # ----------------------------------------------------------------------
        def up_v1_1_0(conn: sqlite3.Connection):
            cursor = conn.cursor()
            # 1. Settings key-value table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # If a rollback backup existed from a previous downgrade, restore it!
            if table_exists(conn, "settings_v1_1_backup"):
                logger.info("Restoring previous settings from rollback backup table...")
                cursor.execute("""
                    INSERT OR REPLACE INTO settings (key, value)
                    SELECT key, value FROM settings_v1_1_backup
                """)
                cursor.execute("DROP TABLE IF EXISTS settings_v1_1_backup;")

            # 2. Add confidence column to detections table non-destructively
            add_column_if_missing(conn, "detections", "confidence", "REAL", default="1.0")

            # 3. Add index on matched_person_id for rapid person history lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_detections_person ON detections(matched_person_id);")

        def down_v1_1_0(conn: sqlite3.Connection):
            # Non-destructive rollback:
            # 1. Back up settings to backup table so they aren't lost if rolled forward again
            if table_exists(conn, "settings"):
                conn.execute("CREATE TABLE IF NOT EXISTS settings_v1_1_backup AS SELECT * FROM settings;")
                conn.execute("DROP TABLE IF EXISTS settings;")
                logger.info("Non-destructive rollback: Preserved settings in settings_v1_1_backup table.")

            # 2. Drop index
            conn.execute("DROP INDEX IF EXISTS idx_detections_person;")

        self.register(MigrationStep(
            migration_id=2,
            version_tag="1.1.0",
            name="dynamic_settings_and_telemetry",
            description="Adds SQLite settings storage and detection confidence telemetry.",
            up_fn=up_v1_1_0,
            down_fn=down_v1_1_0
        ))


# Global Singleton Migration Manager
migration_manager = MigrationManager()

def run_migrations(target_version: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Runs database migrations forward (or back) to match target_version."""
    target = target_version or settings.APP_VERSION
    target_db = db_path or settings.db_path
    return migration_manager.migrate_to_app_version(target, target_db)

def rollback_migrations(target_version: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Rolls back database migrations to match target_version."""
    target_db = db_path or settings.db_path
    return migration_manager.migrate_to_app_version(target_version, target_db)

def get_migration_status(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Returns the current migration state and applied history."""
    target_db = db_path or settings.db_path
    p = Path(target_db)
    if not p.is_file():
        return {
            "current_app_version": settings.APP_VERSION,
            "database_version": "none",
            "applied_migrations": [],
            "available_migrations": [
                {"id": m.migration_id, "version": m.version_tag, "name": m.name, "description": m.description}
                for m in migration_manager.migrations
            ]
        }

    conn = sqlite3.connect(str(p))
    try:
        applied = migration_manager.get_applied_migrations(conn)
        current_version = migration_manager.get_current_app_version(conn)
        return {
            "current_app_version": settings.APP_VERSION,
            "database_version": current_version,
            "applied_migrations": applied,
            "available_migrations": [
                {"id": m.migration_id, "version": m.version_tag, "name": m.name, "description": m.description}
                for m in migration_manager.migrations
            ]
        }
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Household Face Detection Database Migration Tool")
    parser.add_argument("--status", action="store_true", help="Print current migration status")
    parser.add_argument("--forward", type=str, help="Roll forward to target app version (e.g. 1.1.0)")
    parser.add_argument("--rollback", type=str, help="Roll back to target app version (e.g. 1.0.0)")
    args = parser.parse_args()

    if args.status:
        import pprint
        pprint.pprint(get_migration_status())
    elif args.rollback:
        print(f"Rolling back migrations to {args.rollback}...")
        res = rollback_migrations(args.rollback)
        print("Result:", res)
    elif args.forward:
        print(f"Rolling forward migrations to {args.forward}...")
        res = run_migrations(args.forward)
        print("Result:", res)
    else:
        print(f"Running auto-migrations for APP_VERSION: {settings.APP_VERSION}...")
        res = run_migrations()
        print("Result:", res)
