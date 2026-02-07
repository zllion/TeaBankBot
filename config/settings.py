"""Configuration management for TeaBankBot."""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """Configuration settings for TeaBankBot.

    This class centralizes all configuration values, replacing hardcoded
    values throughout the codebase.
    """

    # Discord Configuration (required)
    discord_token: str
    discord_test_token: str

    # Database Configuration
    prod_db_path: str = 'teabank.db'
    test_db_path: str = 'testbank.db'

    # Google Sheets Configuration
    gs_credentials_path: str = './teabank-9ce129712f0c.json'
    prod_sheet_name: str = 'TeaBank'
    test_sheet_name: str = 'TestBank'

    # Business Rules
    max_deposit_amount: int = 1_000_000_000_000  # 1T
    max_request_amount: int = 100_000_000_000  # 100B
    max_transfer_amount: int = 1_000_000_000_000  # 1T
    min_balance: int = -1_000_000_000  # -1B

    # Audit Configuration
    audit_max_output: int = 20
    blocked_channel_ids: List[int] = field(default_factory=lambda: [854068518172229662])

    # Owner Configuration
    owner_id: int = 356096513828454411
    admin_role_name: str = '管理员'

    @classmethod
    def load(cls) -> 'Settings':
        """Load settings from environment variables.

        Returns:
            Settings: A Settings instance with values from environment variables.

        Raises:
            ValueError: If required environment variables are not set.
        """
        discord_token = os.getenv('DISCORD_TOKEN')
        discord_test_token = os.getenv('DISCORD_TOKEN_TEST')

        if not discord_token:
            raise ValueError("DISCORD_TOKEN environment variable is required")
        if not discord_test_token:
            raise ValueError("DISCORD_TOKEN_TEST environment variable is required")

        return cls(
            discord_token=discord_token,
            discord_test_token=discord_test_token,
        )
