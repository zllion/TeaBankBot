"""Tests for BankService deposit operations."""

import sqlite3
import pytest

from src.models.exceptions import AccountNotFoundError, InvalidAmountError
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


def test_deposit_success(bank_service, account_repo, transaction_repo):
    """Deposit creates pending transaction."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Perform deposit
    amount = 1000
    memo = "Test deposit"
    transaction = bank_service.deposit(user_id, amount, memo)

    # Verify transaction was created
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.type == "deposit"
    assert transaction.status == "pending"
    assert transaction.amount == amount
    assert transaction.memo == memo

    # Verify pending balance increased
    account = account_repo.find_by_account_no("234567890")
    assert account.pending == amount

    # Verify amount balance unchanged
    assert account.amount == 0


def test_deposit_account_not_found(bank_service):
    """Should raise AccountNotFoundError."""
    with pytest.raises(AccountNotFoundError) as exc_info:
        bank_service.deposit("9999999999", 100, "Test")

    # Verify the error message contains the account number
    assert "999999999" in str(exc_info.value)  # Last 9 digits


def test_deposit_negative_amount_raises_error(bank_service):
    """Should raise InvalidAmountError with 'negative' in message."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Try to deposit negative amount
    with pytest.raises(InvalidAmountError) as exc_info:
        bank_service.deposit(user_id, -100, "Test")

    # Verify the error message contains 'negative'
    assert "negative" in str(exc_info.value).lower()


def test_deposit_zero_amount_raises_error(bank_service):
    """Should raise InvalidAmountError."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Try to deposit zero amount
    with pytest.raises(InvalidAmountError):
        bank_service.deposit(user_id, 0, "Test")


def test_deposit_exceeds_max_amount(bank_service):
    """Should raise InvalidAmountError (over 1T)."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Try to deposit more than max amount (1T)
    with pytest.raises(InvalidAmountError):
        bank_service.deposit(user_id, 1000000000001, "Test")


def test_deposit_max_allowed_amount(bank_service, account_repo, transaction_repo):
    """1T deposit should succeed."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Deposit max amount (1T)
    max_amount = 1000000000000
    transaction = bank_service.deposit(user_id, max_amount, "Max deposit")

    # Verify transaction was created
    assert transaction is not None
    assert transaction.amount == max_amount

    # Verify pending balance increased
    account = account_repo.find_by_account_no("234567890")
    assert account.pending == max_amount


def test_deposit_minimum_amount(bank_service, account_repo, transaction_repo):
    """1 isk deposit should succeed."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Deposit minimum amount (1)
    min_amount = 1
    transaction = bank_service.deposit(user_id, min_amount, "Min deposit")

    # Verify transaction was created
    assert transaction is not None
    assert transaction.amount == min_amount

    # Verify pending balance increased
    account = account_repo.find_by_account_no("234567890")
    assert account.pending == min_amount


def test_deposit_with_empty_memo(bank_service, account_repo, transaction_repo):
    """Empty memo should work."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Deposit with empty memo
    transaction = bank_service.deposit(user_id, 100, "")

    # Verify transaction was created with empty memo
    assert transaction is not None
    assert transaction.memo == ""


def test_deposit_increases_pending_not_amount(bank_service, account_repo, transaction_repo):
    """Verify pending increases, amount unchanged."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Set initial amount
    account_repo.update_amount("234567890", 500)

    # Deposit
    deposit_amount = 1000
    bank_service.deposit(user_id, deposit_amount, "Test")

    # Verify pending increased, amount unchanged
    account = account_repo.find_by_account_no("234567890")
    assert account.pending == deposit_amount
    assert account.amount == 500  # Unchanged


def test_approve_deposit_updates_balances(bank_service, account_repo, transaction_repo):
    """Approve deposit should update pending and amount."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 500)

    # Deposit
    deposit_amount = 1000
    transaction = bank_service.deposit(user_id, deposit_amount, "Test")

    # Verify pending increased, amount unchanged before approval
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == deposit_amount
    assert account.amount == 500  # Unchanged

    # Approve the transaction
    bank_service.approve_transaction(transaction.id, "admin")

    # Verify pending cleared (back to 0), amount increased
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == 0  # Cleared
    assert account.amount == 1500  # Increased by deposit amount
