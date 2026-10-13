"""Tracked example files must never contain real keys (the repo is public)."""
import unittest
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config"


class NoSecretsInExamples(unittest.TestCase):
    def test_env_example_values_are_empty(self):
        for line in (CONFIG / ".env.example").read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                self.assertEqual(value.strip(), "", f"{key.strip()} must be empty in .env.example")


if __name__ == "__main__":
    unittest.main()
