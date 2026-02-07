"""Tests for BankService remaining operations (request, donate, deny, pull)."""

import sqlite3
import pytest

from src.models.exceptions import (
    AccountNotFoundError,
    InsufficientBalanceError,
    InvalidAmountError,
    TransactionNotFoundError,
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


def test_request_success(bank_service, account_repo, transaction_repo):
    """Request creates pending transaction."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Perform request
    amount = 1000
    memo = "Test request"
    transaction = bank_service.request(user_id, amount, memo)

    # Verify transaction was created
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.type == "request"
    assert transaction.status == "pending"
    assert transaction.amount == amount
    assert transaction.memo == memo

    # Verify pending balance increased
    account = account_repo.find_by_account_no("234567890")
    assert account.pending == amount

    # Verify amount balance unchanged
    assert account.amount == 0


def test_request_exceeds_max_limit(bank_service):
    """Max is 100B (not 1T)."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Try to request more than 100B
    with pytest.raises(InvalidAmountError):
        bank_service.request(user_id, 100000000001, "Test")  # 100B + 1


def test_request_max_allowed_amount(bank_service):
    """100B request should succeed."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Request max amount (100B)
    max_request_amount = 100000000000
    transaction = bank_service.request(user_id, max_request_amount, "Max request")

    # Verify transaction was created
    assert transaction is not None
    assert transaction.amount == max_request_amount
    assert transaction.type == "request"


def test_donate_success(bank_service, account_repo, transaction_repo):
    """Donate decreases pending."""
    # Create an account with some balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 5000)

    # Perform donation
    amount = 1000
    memo = "Test donation"
    transaction = bank_service.donate(user_id, amount, memo)

    # Verify transaction was created
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.type == "donate"
    assert transaction.status == "pending"
    assert transaction.amount == amount
    assert transaction.memo == memo

    # Verify pending balance decreased
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == -amount

    # Verify amount balance unchanged
    assert account.amount == 5000


def test_donate_exceeds_total_balance(bank_service, account_repo):
    """Should raise InsufficientBalanceError."""
    # Create an account with limited balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Set initial amount
    account_repo.update_amount(account_no, 500)

    # Try to donate more than available balance
    with pytest.raises(InsufficientBalanceError):
        bank_service.donate(user_id, 1000, "Test")


def test_deny_transaction_reverts_pending(bank_service, account_repo, transaction_repo):
    """Deny reverts pending."""
    # Create an account first
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)

    # Perform request (increases pending)
    amount = 1000
    transaction = bank_service.request(user_id, amount, "Test request")

    # Verify pending increased
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == amount

    # Deny the transaction
    bank_service.deny_transaction(transaction.id, "admin")

    # Verify pending reverted to 0
    account = account_repo.find_by_account_no(account_no)
    assert account.pending == 0

    # Verify transaction status is denied
    denied_txn = transaction_repo.find_by_id(transaction.id)
    assert denied_txn.status == "denied"


def test_deny_nonexistent_transaction_raises_error(bank_service):
    """Should raise TransactionNotFoundError."""
    with pytest.raises(TransactionNotFoundError):
        bank_service.deny_transaction(999, "admin")


def test_pull_recent_transactions(bank_service, account_repo, transaction_repo):
    """Get N recent transactions."""
    # Create two accounts
    user1 = "1234567890"
    user2 = "9876543210"
    bank_service.create_account(user1, "Alice")
    bank_service.create_account(user2, "Bob")

    # Create multiple transactions for user1
    bank_service.request(user1, 100, "Request 1")
    bank_service.request(user1, 200, "Request 2")
    bank_service.request(user1, 300, "Request 3")

    # Pull recent transactions
    transactions = bank_service.pull_transactions(user1, 2)

    # Verify we got 2 transactions
    assert len(transactions) == 2

    # Verify they are in reverse order (most recent first)
    # Since we're pulling by TransactionID DESC, the last created should be first
    assert transactions[0].amount == 300
    assert transactions[1].amount == 200


def test_pull_transactions_excludes_denied(bank_service, account_repo, transaction_repo):
    """Should exclude denied transactions."""
    # Create an account
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")

    # Create multiple transactions
    txn1 = bank_service.request(user_id, 100, "Request 1")
    txn2 = bank_service.request(user_id, 200, "Request 2")
    bank_service.request(user_id, 300, "Request 3")

    # Deny one transaction
    bank_service.deny_transaction(txn2.id, "admin")

    # Pull transactions
    transactions = bank_service.pull_transactions(user_id, 10)

    # Verify denied transaction is not included
    txn_ids = [t.id for t in transactions]
    assert txn2.id not in txn_ids
    assert txn1.id in txn_ids


def test_get_pending_transactions(bank_service, account_repo, transaction_repo):
    """Get all pending."""
    # Create two accounts
    user1 = "1234567890"
    user2 = "9876543210"
    bank_service.create_account(user1, "Alice")
    bank_service.create_account(user2, "Bob")
    account_no1 = bank_service._get_account_no(user1)

    # Give user1 some initial balance to donate
    account_repo.update_amount(account_no1, 500)

    # Create pending transactions
    bank_service.request(user1, 100, "Request 1")
    bank_service.request(user2, 200, "Request 2")
    bank_service.donate(user1, 50, "Donate 1")

    # Get all pending transactions
    pending = bank_service.get_pending_transactions(limit=10)

    # Verify we got 3 pending transactions
    assert len(pending) == 3

    # Verify all are pending
    for txn in pending:
        assert txn.status == "pending"

    # Verify the types
    types = {txn.type for txn in pending}
    assert types == {"request", "donate"}
