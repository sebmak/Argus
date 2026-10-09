import unittest
import sys
from unittest.mock import MagicMock

if "pydantic" not in sys.modules:
    class DummyBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    pyd_mock = MagicMock()
    pyd_mock.BaseModel = DummyBaseModel
    pyd_mock.Field = lambda *args, **kwargs: None
    sys.modules["pydantic"] = pyd_mock

from app.core.webhook_parser import parse_protect_webhook, WebhookPayload

class TestWebhookParser(unittest.TestCase):
    def setUp(self):
        # User's exact Home Assistant UniFi Protect payload sample
        self.ha_direct_payload = {
            "alarm": {
                "name": "Unlock Door",
                "sources": [{"device": "9041B2E8F6B4", "type": "include"}],
                "conditions": [{"condition": {"type": "is", "source": "face_known"}}],
                "triggers": [
                    {
                        "device": "9041B2E8F6B4",
                        "value": "Sebastian",
                        "key": "face_known",
                        "group": {"name": "Sebastian"},
                        "zones": {"loiter": [], "zone": [1], "line": [], "package": []},
                        "eventId": "5961b6af-fb42-4978-926b-1fc8ffeea032",
                        "timestamp": 1791428432008,
                        "sourceEvent": {
                            "camera": "6ac3b97a03b0c603e4000659",
                            "createdAt": "2026-10-08T03:00:29.245728273Z",
                            "device": "6ac3b97a03b0c603e4000659",
                            "id": "5961b6af-fb42-4978-926b-1fc8ffeea032",
                            "score": 85,
                            "smartDetectTypes": ["face", "person"]
                        }
                    }
                ],
                "thumbnail": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/"
            }
        }

        # Wrapped inside trigger.json (when HA webhook passes full trigger state)
        self.ha_wrapped_trigger = {
            "trigger": {
                "platform": "webhook",
                "webhook_id": "-sA35zrm3M7RX4lZabVEgXs27",
                "json": {
                    "triggers": [
                        {
                            "value": "Sebastian",
                            "group": {"name": "Sebastian"},
                            "eventId": "5961b6af-fb42-4978-926b-1fc8ffeea032",
                            "sourceEvent": {
                                "camera": "front_door_cam",
                                "score": 92
                            }
                        }
                    ],
                    "thumbnail": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/"
                }
            }
        }

        # Flat payload
        self.flat_payload = {
            "person_name": "Sebastian",
            "snapshot": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/",
            "camera_id": "backyard_g4",
            "confidence": 0.88,
            "event_id": "evt_998877"
        }

    def test_parse_ha_wrapped_trigger(self):
        parsed = parse_protect_webhook(self.ha_wrapped_trigger)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.person_name, "Sebastian")
        self.assertEqual(parsed.camera_id, "front_door_cam")
        self.assertEqual(parsed.event_id, "5961b6af-fb42-4978-926b-1fc8ffeea032")
        self.assertEqual(parsed.confidence, 0.92)
        self.assertTrue(parsed.image_base64.startswith("data:image/jpeg;base64,"))

    def test_parse_ha_direct_payload(self):
        # Even if wrapped inside alarm or direct json
        parsed = parse_protect_webhook(self.ha_direct_payload["alarm"])
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.person_name, "Sebastian")
        self.assertEqual(parsed.camera_id, "6ac3b97a03b0c603e4000659")
        self.assertEqual(parsed.event_id, "5961b6af-fb42-4978-926b-1fc8ffeea032")
        self.assertEqual(parsed.confidence, 0.85)

    def test_parse_flat_payload(self):
        parsed = parse_protect_webhook(self.flat_payload)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.person_name, "Sebastian")
        self.assertEqual(parsed.camera_id, "backyard_g4")
        self.assertEqual(parsed.event_id, "evt_998877")
        self.assertEqual(parsed.confidence, 0.88)

    def test_missing_image_returns_none(self):
        invalid_payload = {"person_name": "Sebastian"}
        parsed = parse_protect_webhook(invalid_payload)
        self.assertIsNone(parsed)

    def test_missing_name_returns_none(self):
        invalid_payload = {"snapshot": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."}
        parsed = parse_protect_webhook(invalid_payload)
        self.assertIsNone(parsed)

if __name__ == "__main__":
    unittest.main()
