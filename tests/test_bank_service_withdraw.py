"""Tests for BankService withdraw operations."""

import sqlite3
import pytest

from src.models.exceptions import (
    AccountNotFoundError,
    InvalidAmountError,
    InsufficientBalanceError,
)
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


def test_withdraw_success(bank_service, account_repo, transaction_repo):
    """Withdraw from funded account."""
    # Create an account with initial balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 5000)

    # Perform withdraw
    amount = 1000
    memo = "Test withdraw"
    transaction = bank_service.withdraw(user_id, amount, memo)

    # Verify transaction was created
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.type == "withdraw"
    assert transaction.status == "pending"
    assert transaction.amount == amount
    assert transaction.memo == memo

    # Verify pending balance decreased (withdraw reduces pending)
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == -amount
    # Verify amount balance unchanged
    assert account.amount == 5000


def test_withdraw_account_not_found(bank_service):
    """Should raise AccountNotFoundError."""
    with pytest.raises(AccountNotFoundError) as exc_info:
        bank_service.withdraw("9999999999", 100, "Test")

    # Verify the error message contains the account number
    assert "999999999" in str(exc_info.value)  # Last 9 digits


def test_withdraw_negative_amount_raises_error(bank_service):
    """Should raise InvalidAmountError."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Try to withdraw negative amount
    with pytest.raises(InvalidAmountError) as exc_info:
        bank_service.withdraw(user_id, -100, "Test")

    # Verify the error message contains 'negative'
    assert "negative" in str(exc_info.value).lower()


def test_withdraw_exceeds_max_amount(bank_service):
    """Should raise InvalidAmountError."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Try to withdraw more than max amount (1T)
    with pytest.raises(InvalidAmountError):
        bank_service.withdraw(user_id, 1000000000001, "Test")


def test_withdraw_insufficient_balance(bank_service, account_repo):
    """Should raise InsufficientBalanceError."""
    # Create an account with small balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 500)

    # Try to withdraw more than available
    with pytest.raises(InsufficientBalanceError):
        bank_service.withdraw(user_id, 1000, "Test")


def test_withdraw_exact_balance(bank_service, account_repo, transaction_repo):
    """Withdraw exact amount."""
    # Create an account with initial balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 1000)

    # Withdraw exact amount
    amount = 1000
    transaction = bank_service.withdraw(user_id, amount, "Exact withdraw")

    # Verify transaction was created
    assert transaction is not None
    assert transaction.amount == amount

    # Verify pending balance decreased
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == -amount


def test_withdraw_with_pending_included(bank_service, account_repo):
    """Balance check includes pending."""
    # Create an account with initial balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount and pending (from previous pending withdrawals)
    account_repo.update_amount(account_no, 1000)
    account_repo.update_pending(account_no, -200)  # Pending withdrawal

    # Available: 1000 - 200 = 800
    # Try to withdraw 800 (should succeed)
    transaction = bank_service.withdraw(user_id, 800, "Test")

    # Verify transaction was created
    assert transaction is not None
    assert transaction.amount == 800

    # Verify pending balance decreased further
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == -1000  # -200 + (-800)


def test_withdraw_decreases_pending(bank_service, account_repo, transaction_repo):
    """Withdraw decreases pending, not amount."""
    # Create an account with initial balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 5000)

    # Withdraw
    withdraw_amount = 1000
    bank_service.withdraw(user_id, withdraw_amount, "Test")

    # Verify pending decreased, amount unchanged
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == -withdraw_amount
    assert account.amount == 5000  # Unchanged


def test_approve_withdrawal_updates_balances(bank_service, account_repo, transaction_repo):
    """Approve withdrawal should update pending and amount."""
    # Create an account with initial balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 5000)

    # Withdraw
    withdraw_amount = 1000
    transaction = bank_service.withdraw(user_id, withdraw_amount, "Test")

    # Verify pending decreased, amount unchanged before approval
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == -withdraw_amount
    assert account.amount == 5000  # Unchanged

    # Approve the transaction
    bank_service.approve_transaction(transaction.id, "admin")

    # Verify pending restored (back to 0), amount decreased
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == 0  # Restored
    assert account.amount == 4000  # Decreased by withdrawal amount
