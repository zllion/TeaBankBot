"""Tests for BankService account operations."""

import sqlite3
import pytest

from src.models.account import Account
from src.models.exceptions import AccountAlreadyExistsError, AccountNotFoundError
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.services.bank_service import BankService


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def account_repo(in_memory_db):
    """Create an AccountRepository instance with a fresh database."""
    repo = AccountRepository(in_memory_db)
    repo.create_table()
    return repo


@pytest.fixture
def transaction_repo(in_memory_db):
    """Create a TransactionRepository instance with a fresh database."""
    repo = TransactionRepository(in_memory_db)
    repo.create_table()
    return repo


@pytest.fixture
def bank_service(account_repo, transaction_repo):
    """Create a BankService instance with repositories."""
    return BankService(account_repo=account_repo, transaction_repo=transaction_repo)


def test_create_account_success(bank_service, account_repo):
    """Create account, verify fields."""
    # Create an account with a 10-digit user_id
    user_id = "1234567890"
    name = "Alice"

    bank_service.create_account(user_id, name)

    # Verify the account was created with the correct account_no (last 9 digits)
    account = account_repo.find_by_account_no("234567890")
    assert account is not None
    assert account.account_no == "234567890"  # Last 9 digits of user_id
    assert account.name == "Alice"
    assert account.amount == 0
    assert account.pending == 0
    assert account.share == 0


def test_create_duplicate_account_raises_error(bank_service):
    """Should raise AccountAlreadyExistsError."""
    user_id = "1234567890"
    name = "Alice"

    # First creation should succeed
    bank_service.create_account(user_id, name)

    # Second creation with same user_id should fail
    with pytest.raises(AccountAlreadyExistsError) as exc_info:
        bank_service.create_account(user_id, "Bob")

    # Verify the error message contains the account number
    assert "234567890" in str(exc_info.value)


def test_get_balance_success(bank_service, account_repo):
    """Get balance, verify returns (amount, pending)."""
    # Create an account with some balance
    user_id = "1234567890"
    name = "Alice"
    bank_service.create_account(user_id, name)

    # Set some balance values
    account_repo.update_amount("234567890", 100)
    account_repo.update_pending("234567890", 50)

    # Get balance
    amount, pending = bank_service.get_balance(user_id)

    # Verify the return values
    assert amount == 100
    assert pending == 50


def test_get_balance_account_not_found(bank_service):
    """Should raise AccountNotFoundError."""
    # Try to get balance for a non-existent account
    with pytest.raises(AccountNotFoundError) as exc_info:
        bank_service.get_balance("9999999999")

    # Verify the error message contains the account number
    assert "999999999" in str(exc_info.value)  # Last 9 digits


def test_account_no_truncated_from_user_id(bank_service, account_repo):
    """Account number should be last 9 digits of user_id."""
    # Test with various user_id lengths (using non-overlapping user IDs)
    # Note: _get_account_no always takes last 9 digits maximum
    test_cases = [
        ("9876543210", "876543210"),  # 10 digits -> last 9
        ("52345678901", "345678901"),  # 11 digits -> last 9
        ("111111111", "111111111"),  # 9 digits -> all 9
        ("22222222", "22222222"),  # 8 digits -> all 8
        ("3", "3"),  # 1 digit -> 1 digit
    ]

    for user_id, expected_account_no in test_cases:
        # Create account
        bank_service.create_account(user_id, f"User{user_id}")

        # Verify the account_no is correct
        account = account_repo.find_by_account_no(expected_account_no)
        assert account is not None, f"Failed to find account {expected_account_no} for user_id {user_id}"
        assert account.account_no == expected_account_no


def test_get_or_create_account_gets_existing(bank_service, account_repo):
    """Test _get_or_create_account returns existing account."""
    # Create an account directly in the repo
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=50,
        share=0,
    )
    account_repo.create(account)

    # Call _get_or_create_account - should return existing account
    result = bank_service._get_or_create_account("123456789", "Bob")

    # Should return the existing account with original name
    assert result.account_no == "123456789"
    assert result.name == "Alice"  # Original name preserved
    assert result.amount == 100
    assert result.pending == 50


def test_get_or_create_account_creates_new(bank_service, account_repo):
    """Test _get_or_create_account creates new account if not exists."""
    # Call _get_or_create_account for non-existent account
    result = bank_service._get_or_create_account("123456789", "Alice")

    # Should create and return new account
    assert result.account_no == "123456789"
    assert result.name == "Alice"
    assert result.amount == 0
    assert result.pending == 0
    assert result.share == 0

    # Verify it's in the repo
    found = account_repo.find_by_account_no("123456789")
    assert found is not None
