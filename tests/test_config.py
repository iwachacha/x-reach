# -*- coding: utf-8 -*-
"""Tests for X Reach config module."""

import pytest

from x_reach.config import Config


@pytest.fixture
def tmp_config(tmp_path):
    return Config(config_path=tmp_path / "config.yaml")


class TestConfig:
    def test_init_creates_dir(self, tmp_path):
        config_file = tmp_path / "subdir" / "config.yaml"
        Config(config_path=config_file)
        assert config_file.parent.exists()

    def test_set_and_get(self, tmp_config):
        tmp_config.set("test_key", "test_value")
        assert tmp_config.get("test_key") == "test_value"

    def test_get_default(self, tmp_config):
        assert tmp_config.get("nonexistent") is None
        assert tmp_config.get("nonexistent", "default") == "default"

    def test_get_from_env(self, tmp_config, monkeypatch):
        monkeypatch.setenv("TEST_ENV_KEY", "env_value")
        assert tmp_config.get("test_env_key") == "env_value"

    def test_get_uses_known_env_aliases(self, tmp_config, monkeypatch):
        monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("TWITTER_CT0", raising=False)
        monkeypatch.setenv("AUTH_TOKEN", "auth-token")
        monkeypatch.setenv("CT0", "ct0-token")

        assert tmp_config.get("twitter_auth_token") == "auth-token"
        assert tmp_config.get("twitter_ct0") == "ct0-token"

    def test_config_file_priority_over_env(self, tmp_config, monkeypatch):
        monkeypatch.setenv("MY_KEY", "from_env")
        tmp_config.set("my_key", "from_config")
        assert tmp_config.get("my_key") == "from_config"

    def test_save_and_load(self, tmp_config):
        tmp_config.set("key1", "value1")
        tmp_config.set("key2", 42)

        config2 = Config(config_path=tmp_config.config_path)
        assert config2.get("key1") == "value1"
        assert config2.get("key2") == 42

    def test_default_location_does_not_fall_back_to_legacy_config(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("AUTH_TOKEN", raising=False)
        config_dir = tmp_path / ".x-reach"
        config_file = config_dir / "config.yaml"
        legacy_dir = tmp_path / ".agent-reach"
        legacy_file = legacy_dir / "config.yaml"
        legacy_dir.mkdir(parents=True)
        legacy_file.write_text("twitter_auth_token: legacy-token\n", encoding="utf-8")

        monkeypatch.setattr(Config, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(Config, "CONFIG_FILE", config_file)
        monkeypatch.setattr(Config, "LEGACY_CONFIG_DIR", legacy_dir)
        monkeypatch.setattr(Config, "LEGACY_CONFIG_FILE", legacy_file)

        config = Config()

        assert config.config_path == config_file
        assert config.get("twitter_auth_token") is None

    def test_delete(self, tmp_config):
        tmp_config.set("to_delete", "value")
        assert tmp_config.get("to_delete") == "value"
        tmp_config.delete("to_delete")
        assert tmp_config.get("to_delete") is None

    def test_is_configured(self, tmp_config, monkeypatch):
        monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("TWITTER_CT0", raising=False)
        monkeypatch.delenv("AUTH_TOKEN", raising=False)
        monkeypatch.delenv("CT0", raising=False)
        assert not tmp_config.is_configured("twitter")
        tmp_config.set("twitter_auth_token", "auth-token")
        tmp_config.set("twitter_ct0", "ct0-token")
        assert tmp_config.is_configured("twitter")

    def test_get_configured_features(self, tmp_config, monkeypatch):
        monkeypatch.delenv("TWITTER_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("TWITTER_CT0", raising=False)
        monkeypatch.delenv("AUTH_TOKEN", raising=False)
        monkeypatch.delenv("CT0", raising=False)
        features = tmp_config.get_configured_features()
        assert features == {"twitter": False}

    def test_to_dict_masks_sensitive(self, tmp_config):
        tmp_config.set("api_key", "super-secret-key-12345")
        tmp_config.set("service_client_secret", "client-secret-12345")
        tmp_config.set("normal_setting", "visible")
        masked = tmp_config.to_dict()
        assert masked["api_key"] == "super-se..."
        assert masked["service_client_secret"] == "client-s..."
        assert masked["normal_setting"] == "visible"

