import unittest
import sys
import sqlite3
import shutil
from pathlib import Path
from unittest.mock import MagicMock

# Graceful mocks for host environment
for mod in ["cv2", "numpy", "httpx", "paho", "paho.mqtt", "paho.mqtt.client", "fastapi", "fastapi.security", "jose"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

bcrypt_mock = MagicMock()
bcrypt_mock.gensalt.return_value = b"$2b$12$e0abcdef12345678901234"
bcrypt_mock.hashpw.return_value = b"$2b$12$hashedpasswordmockmockmock"
sys.modules["bcrypt"] = bcrypt_mock

if "pydantic" not in sys.modules:
    class DummyBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self, **kwargs):
            return self.__dict__
    pyd_mock = MagicMock()
    pyd_mock.BaseModel = DummyBaseModel
    pyd_mock.BaseSettings = DummyBaseModel
    pyd_mock.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = pyd_mock
    sys.modules["pydantic_settings"] = pyd_mock

from app.config import settings
from app.db.migrations import (
    MigrationManager,
    MigrationStep,
    table_exists,
    column_exists,
    add_column_if_missing,
    backup_database,
    parse_version_tuple,
    run_migrations,
    rollback_migrations,
    get_migration_status
)
from app.db.database import init_db, seed_default_settings

# ==============================================================================
# Rules for TestDatabaseMigrations:
# 1. Tests database schema migrations, roll-forwards, roll-backs, and backup restorations.
# 2. Member variables must be declared at the top of the class.
# 3. Each test must use isolated temporary directories and clean up afterwards.
# ==============================================================================
class TestDatabaseMigrations(unittest.TestCase):
    test_dir: Path
    db_path: str

    def setUp(self):
        self.test_dir = Path("data/test_migrations_dir")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(self.test_dir / "test_faces.db")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_version_tuple_parsing(self):
        self.assertEqual(parse_version_tuple("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version_tuple("1.1.0"), (1, 1, 0))
        self.assertEqual(parse_version_tuple("2.0.0-beta"), (2, 0, 0))
        self.assertTrue(parse_version_tuple("1.0.0") < parse_version_tuple("1.1.0"))
        self.assertTrue(parse_version_tuple("1.1.0") > parse_version_tuple("1.0.0"))

    def test_fresh_database_migration_to_1_1_0(self):
        manager = MigrationManager()
        result = manager.migrate_to_app_version("1.1.0", self.db_path)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["current_app_version"], "1.1.0")
        self.assertIn("initial_household_schema", result["applied"])
        self.assertIn("dynamic_settings_and_telemetry", result["applied"])

        # Inspect database tables and columns
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertTrue(table_exists(conn, "persons"))
            self.assertTrue(table_exists(conn, "face_samples"))
            self.assertTrue(table_exists(conn, "detections"))
            self.assertTrue(table_exists(conn, "users"))
            self.assertTrue(table_exists(conn, "settings"))
            self.assertTrue(table_exists(conn, "schema_migrations"))
            self.assertTrue(column_exists(conn, "detections", "confidence"))
        finally:
            conn.close()

    def test_non_destructive_rollback_and_forward(self):
        manager = MigrationManager()
        # 1. Migrate to 1.1.0
        manager.migrate_to_app_version("1.1.0", self.db_path)

        # Insert sample person and custom setting
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO persons (id, name, notes) VALUES (?, ?, ?)", ("p_1", "Sebastian", "Resident"))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("custom_key", "custom_val"))
        conn.commit()
        conn.close()

        # 2. Rollback to 1.0.0 (e.g. server downgraded)
        rollback_res = manager.migrate_to_app_version("1.0.0", self.db_path)
        self.assertEqual(rollback_res["status"], "success")
        self.assertEqual(rollback_res["current_app_version"], "1.0.0")
        self.assertIn("dynamic_settings_and_telemetry", rollback_res["rolled_back"])
        self.assertIsNotNone(rollback_res["backup_path"])

        # Verify core person data was NOT destroyed!
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM persons WHERE id = 'p_1'")
            self.assertEqual(cursor.fetchone()[0], "Sebastian")

            # Active settings table was backed up to settings_v1_1_backup
            self.assertFalse(table_exists(conn, "settings"))
            self.assertTrue(table_exists(conn, "settings_v1_1_backup"))
            cursor.execute("SELECT value FROM settings_v1_1_backup WHERE key = 'custom_key'")
            self.assertEqual(cursor.fetchone()[0], "custom_val")
        finally:
            conn.close()

        # 3. Roll forward back to 1.1.0
        forward_res = manager.migrate_to_app_version("1.1.0", self.db_path)
        self.assertEqual(forward_res["status"], "success")
        self.assertEqual(forward_res["current_app_version"], "1.1.0")

        # Verify custom settings were restored from backup table
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            self.assertTrue(table_exists(conn, "settings"))
            cursor.execute("SELECT value FROM settings WHERE key = 'custom_key'")
            self.assertEqual(cursor.fetchone()[0], "custom_val")
        finally:
            conn.close()

    def test_backfill_preexisting_unversioned_database(self):
        # Create unversioned pre-existing database manually
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE persons (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL);")
        conn.execute("CREATE TABLE face_samples (id TEXT PRIMARY KEY, person_id TEXT);")
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
        conn.execute("INSERT INTO persons (id, name) VALUES ('p_existing', 'Existing User');")
        conn.commit()
        conn.close()

        # Run migration manager on pre-existing database
        manager = MigrationManager()
        result = manager.migrate_to_app_version("1.1.0", self.db_path)
        self.assertEqual(result["status"], "success")

        # Verify pre-existing data is intact and migrations table is populated
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM persons WHERE id = 'p_existing'")
            self.assertEqual(cursor.fetchone()[0], "Existing User")

            cursor.execute("SELECT migration_id FROM schema_migrations ORDER BY migration_id ASC")
            ids = [r[0] for r in cursor.fetchall()]
            self.assertIn(1, ids)
            self.assertIn(2, ids)
        finally:
            conn.close()

    def test_boot_migration_with_semver_0_0_x(self):
        """Tests that server boot migration with version like 0.0.6 applies all migrations and does not rollback."""
        manager = MigrationManager()
        # Call migrate_to_app_version in boot mode (allow_rollback=False, apply_all_unapplied=True)
        result = manager.migrate_to_app_version(
            target_app_version="0.0.6",
            db_path=self.db_path,
            allow_rollback=False,
            apply_all_unapplied=True
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["rolled_back"]), 0)
        self.assertIn("initial_household_schema", result["applied"])
        self.assertIn("dynamic_settings_and_telemetry", result["applied"])

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertTrue(table_exists(conn, "settings"))
            self.assertTrue(table_exists(conn, "persons"))
        finally:
            conn.close()

    def test_recovery_from_settings_backup_table(self):
        """Tests automatic restoration of settings from settings_v1_1_backup if a rollback occurred."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE schema_migrations (id INTEGER PRIMARY KEY, migration_id INTEGER UNIQUE, app_version TEXT, name TEXT, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        conn.execute("INSERT INTO schema_migrations (migration_id, app_version, name) VALUES (1, '1.0.0', 'initial_household_schema');")
        conn.execute("CREATE TABLE settings_v1_1_backup (key TEXT PRIMARY KEY, value TEXT);")
        conn.execute("INSERT INTO settings_v1_1_backup (key, value) VALUES ('preserved_key', 'preserved_val');")
        conn.commit()
        conn.close()

        manager = MigrationManager()
        result = manager.migrate_to_app_version(
            target_app_version="0.0.6",
            db_path=self.db_path,
            allow_rollback=False,
            apply_all_unapplied=True
        )

        self.assertEqual(result["status"], "success")
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertTrue(table_exists(conn, "settings"))
            self.assertFalse(table_exists(conn, "settings_v1_1_backup"))
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'preserved_key'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "preserved_val")
        finally:
            conn.close()

    def test_server_startup_with_app_version_0_0_6_and_seed_settings(self):
        """
        Tests that when server starts with APP_VERSION='0.0.6' on a database that had
        a rollback backup table 'settings_v1_1_backup', init_db() and seed_default_settings()
        succeed without any sqlite3 errors and completely restore settings.
        """
        orig_config_dir = settings.CONFIG_DIR
        orig_data_dir = settings.DATA_DIR
        try:
            settings.CONFIG_DIR = str(self.test_dir)
            settings.DATA_DIR = str(self.test_dir)

            # Pre-populate database with settings_v1_1_backup and baseline schema
            conn = sqlite3.connect(settings.db_path)
            conn.execute("CREATE TABLE schema_migrations (id INTEGER PRIMARY KEY, migration_id INTEGER UNIQUE, app_version TEXT, name TEXT, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            conn.execute("INSERT INTO schema_migrations (migration_id, app_version, name) VALUES (1, '1.0.0', 'initial_household_schema');")
            conn.execute("CREATE TABLE settings_v1_1_backup (key TEXT PRIMARY KEY, value TEXT);")
            conn.execute("INSERT INTO settings_v1_1_backup (key, value) VALUES ('notification_threshold', '0.75');")
            conn.commit()
            conn.close()

            # Execute server boot sequence (same as lifespan in app/main.py)
            init_res = init_db(target_version="0.0.6")
            self.assertEqual(init_res["status"], "success")
            # Should NOT have rolled back
            self.assertEqual(len(init_res["rolled_back"]), 0)

            # seed_default_settings must not raise sqlite3.OperationalError: no such table: settings
            seed_default_settings()

            # Verify settings table exists and preserved value is intact
            conn = sqlite3.connect(settings.db_path)
            try:
                self.assertTrue(table_exists(conn, "settings"))
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = 'notification_threshold'")
                row = cursor.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "0.75")

                # Verify default settings are also seeded
                cursor.execute("SELECT value FROM settings WHERE key = 'detection_confidence'")
                row_det = cursor.fetchone()
                self.assertIsNotNone(row_det)
            finally:
                conn.close()
        finally:
            settings.CONFIG_DIR = orig_config_dir
            settings.DATA_DIR = orig_data_dir

if __name__ == "__main__":
    unittest.main()

