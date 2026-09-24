# coding: utf-8
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from trading_v2.config import AppSettings
from trading_v2.domain import TradingMode


class TradingV2SettingsTest(unittest.TestCase):
    def test_local_env_overrides_shared_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root / ".env"
            local = root / ".env.local"
            shared.write_text("TRADING_V2_MODEL_NAME=shared-model\n", encoding="utf-8")
            local.write_text("TRADING_V2_MODEL_NAME=local-model\n", encoding="utf-8")
            settings = AppSettings(_env_file=(shared, local))

        self.assertEqual(settings.model_name, "local-model")

    def test_environment_variables_override_defaults(self) -> None:
        environment = {
            "TRADING_V2_PORT": "8123",
            "TRADING_V2_TRADING_MODE": "paper",
            "TRADING_V2_ENVIRONMENT": "production",
            "TRADING_V2_DOCS_ENABLED": "false",
        }
        with patch.dict(os.environ, environment, clear=False):
            settings = AppSettings(_env_file=None)

        self.assertEqual(settings.port, 8123)
        self.assertEqual(settings.trading_mode, TradingMode.PAPER)
        self.assertEqual(settings.environment, "production")
        self.assertFalse(settings.docs_enabled)

    def test_api_prefix_is_normalized(self) -> None:
        settings = AppSettings(api_prefix="/custom/", _env_file=None)
        self.assertEqual(settings.api_prefix, "/custom")

        with self.assertRaises(ValidationError):
            AppSettings(api_prefix="invalid", _env_file=None)


if __name__ == "__main__":
    unittest.main()
