import os
import sys
import unittest
from unittest.mock import MagicMock

class MockHTTPException(Exception):
    def __init__(self, status_code=400, detail="", headers=None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}

for mod in ["cv2", "httpx", "paho", "paho.mqtt", "paho.mqtt.client", "fastapi", "fastapi.security", "jose"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            m = MagicMock()
            if mod == "fastapi":
                m.HTTPException = MockHTTPException
                m.status = MagicMock()
                m.status.HTTP_429_TOO_MANY_REQUESTS = 429
                m.status.HTTP_401_UNAUTHORIZED = 401
                m.status.HTTP_400_BAD_REQUEST = 400
            sys.modules[mod] = m

os.environ["DATA_DIR"] = "./data_test_auth"
os.environ["CONFIG_DIR"] = "./data_test_auth"

from app.config import settings
from app.db.database import (
    init_db,
    verify_user_credentials,
    update_user_password,
    is_default_password_used,
    get_user_by_username
)
from app.core.rate_limiter import (
    check_login_rate_limit,
    record_login_failure,
    record_login_success,
    _login_attempts
)

class TestAuthSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        _login_attempts.clear()

    def test_rate_limiter_lockout_mechanism(self):
        """Test rate limiter tracking and lockout."""
        ip = "192.168.1.99"
        
        # 4 failures: not locked out yet
        for i in range(4):
            fails, locked = record_login_failure(ip)
            self.assertEqual(fails, i + 1)
            self.assertFalse(locked)

        # 5th failure: locks out!
        fails, locked = record_login_failure(ip)
        self.assertEqual(fails, 5)
        self.assertTrue(locked)

        # check_login_rate_limit should raise HTTPException with 429
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            check_login_rate_limit(ip)
        self.assertEqual(ctx.exception.status_code, 429)

        # Successful login resets the counter
        record_login_success(ip)
        self.assertNotIn(ip, _login_attempts)

    def test_password_update_and_default_detection(self):
        """Test password update function and default password detector."""
        user = get_user_by_username("admin")
        if not user:
            from app.db.database import create_user
            create_user("admin", settings.DEFAULT_ADMIN_PASSWORD)
            user = get_user_by_username("admin")

        self.assertIsNotNone(user)

        # Initial admin uses default password
        self.assertTrue(is_default_password_used(user))

        # Update to strong password
        new_pw = "SuperStrongPassword2026!"
        updated = update_user_password(user["id"], new_pw)
        self.assertTrue(updated)

        # Verify old password fails, new password succeeds
        self.assertIsNone(verify_user_credentials("admin", "admin123"))
        updated_user = verify_user_credentials("admin", new_pw)
        self.assertIsNotNone(updated_user)

        # Is no longer using default password
        self.assertFalse(is_default_password_used(updated_user))

        # Reset back for other tests
        update_user_password(user["id"], "admin123")
        reverted_user = verify_user_credentials("admin", "admin123")
        self.assertTrue(is_default_password_used(reverted_user))

    def tearDown(self):
        _login_attempts.clear()
        if os.path.exists("./data_test_auth"):
            import shutil
            shutil.rmtree("./data_test_auth", ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
