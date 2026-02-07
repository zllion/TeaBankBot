"""Tests for AccountRepository."""

import sqlite3
import pytest

from src.models.account import Account
from src.models.exceptions import AccountAlreadyExistsError
from src.repositories.account_repo import AccountRepository


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


def test_create_table(account_repo):
    """Verify Accounts table is created."""
    # Query sqlite_master to check if table exists
    cursor = account_repo._conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Accounts'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "Accounts"

    # Verify columns
    cursor.execute("PRAGMA table_info(Accounts)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns == {
        "id": "INTEGER",
        "Account": "TEXT",
        "Name": "TEXT",
        "Amount": "INTEGER",
        "Pending": "INTEGER",
        "Share": "INTEGER",
    }


def test_create_account(account_repo):
    """Create account, then find by account_no."""
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=50,
        share=0,
    )

    account_repo.create(account)

    # Find the account
    found = account_repo.find_by_account_no("123456789")
    assert found is not None
    assert found.id == 1
    assert found.account_no == "123456789"
    assert found.name == "Alice"
    assert found.amount == 100
    assert found.pending == 50
    assert found.share == 0


def test_create_duplicate_account(account_repo):
    """Should raise AccountAlreadyExistsError."""
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=0,
        share=0,
    )

    # First creation should succeed
    account_repo.create(account)

    # Second creation with same account_no should fail
    duplicate = Account(
        id=2,
        account_no="123456789",
        name="Bob",
        amount=200,
        pending=0,
        share=0,
    )

    with pytest.raises(AccountAlreadyExistsError):
        account_repo.create(duplicate)


def test_find_by_account_no_not_found(account_repo):
    """Should return None."""
    result = account_repo.find_by_account_no("nonexistent")
    assert result is None


def test_exists(account_repo):
    """Check account exists/doesn't exist."""
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=0,
        share=0,
    )

    # Account doesn't exist yet
    assert account_repo.exists("123456789") is False

    # Create the account
    account_repo.create(account)

    # Now it should exist
    assert account_repo.exists("123456789") is True

    # Different account still doesn't exist
    assert account_repo.exists("987654321") is False


def test_update_pending(account_repo):
    """Update pending balance."""
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=50,
        share=0,
    )

    account_repo.create(account)

    # Add 25 to pending
    account_repo.update_pending("123456789", 25)

    # Verify the update
    found = account_repo.find_by_account_no("123456789")
    assert found.pending == 75
    assert found.amount == 100  # amount should be unchanged


def test_update_amount(account_repo):
    """Update amount balance."""
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=50,
        share=0,
    )

    account_repo.create(account)

    # Add 30 to amount
    account_repo.update_amount("123456789", 30)

    # Verify the update
    found = account_repo.find_by_account_no("123456789")
    assert found.amount == 130
    assert found.pending == 50  # pending should be unchanged


def test_update_pending_and_amount(account_repo):
    """Update both atomically (for audit approval)."""
    account = Account(
        id=1,
        account_no="123456789",
        name="Alice",
        amount=100,
        pending=50,
        share=0,
    )

    account_repo.create(account)

    # Update both: subtract from pending, add to amount (audit approval)
    account_repo.update_pending_and_amount("123456789", pending_delta=-50, amount_delta=50)

    # Verify the atomic update
    found = account_repo.find_by_account_no("123456789")
    assert found.pending == 0  # 50 - 50 = 0
    assert found.amount == 150  # 100 + 50 = 150
