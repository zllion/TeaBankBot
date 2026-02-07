"""Tests for configuration management."""
import os
import pytest
from config.settings import Settings


def test_settings_load(monkeypatch):
    """Test loading Settings from environment variables."""
    # Set environment variables
    monkeypatch.setenv('DISCORD_TOKEN', 'test_discord_token_123')
    monkeypatch.setenv('DISCORD_TOKEN_TEST', 'test_discord_test_token_456')

    # Load settings
    settings = Settings.load()

    # Verify required fields are loaded
    assert settings.discord_token == 'test_discord_token_123'
    assert settings.discord_test_token == 'test_discord_test_token_456'


def test_settings_defaults():
    """Test that all default values are correctly set."""
    settings = Settings(
        discord_token='test_token',
        discord_test_token='test_test_token',
    )

    # Database defaults
    assert settings.prod_db_path == 'teabank.db'
    assert settings.test_db_path == 'testbank.db'

    # Google Sheets defaults
    assert settings.gs_credentials_path == './teabank-9ce129712f0c.json'
    assert settings.prod_sheet_name == 'TeaBank'
    assert settings.test_sheet_name == 'TestBank'

    # Business rules defaults
    assert settings.max_deposit_amount == 1_000_000_000_000  # 1T
    assert settings.max_request_amount == 100_000_000_000  # 100B
    assert settings.max_transfer_amount == 1_000_000_000_000  # 1T
    assert settings.min_balance == -1_000_000_000  # -1B

    # Audit defaults
    assert settings.audit_max_output == 20
    assert settings.blocked_channel_ids == [854068518172229662]

    # Owner defaults
    assert settings.owner_id == 356096513828454411
    assert settings.admin_role_name == '管理员'


def test_settings_load_missing_discord_token(monkeypatch):
    """Test that loading fails when DISCORD_TOKEN is missing."""
    monkeypatch.setenv('DISCORD_TOKEN_TEST', 'test_token')
    monkeypatch.delenv('DISCORD_TOKEN', raising=False)

    with pytest.raises(ValueError, match="DISCORD_TOKEN environment variable is required"):
        Settings.load()


def test_settings_load_missing_discord_test_token(monkeypatch):
    """Test that loading fails when DISCORD_TOKEN_TEST is missing."""
    monkeypatch.setenv('DISCORD_TOKEN', 'test_token')
    monkeypatch.delenv('DISCORD_TOKEN_TEST', raising=False)

    with pytest.raises(ValueError, match="DISCORD_TOKEN_TEST environment variable is required"):
        Settings.load()
