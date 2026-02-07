"""Tests for BankService transfer operations."""

import sqlite3
import pytest

from src.models.exceptions import (
    AccountNotFoundError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidTransferError,
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


def test_transfer_success(bank_service, account_repo, transaction_repo):
    """Transfer between accounts."""
    # Create sender with initial balance
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, 10000)

    # Create receiver
    receiver_id = "2222222222"
    bank_service.create_account(receiver_id, "Bob")
    receiver_account_no = bank_service._get_account_no(receiver_id)

    # Perform transfer
    amount = 5000
    memo = "Test transfer"
    transaction = bank_service.transfer(sender_id, receiver_id, amount, memo)

    # Verify transaction was created with status='done'
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.type == "transfer"
    assert transaction.status == "done"
    assert transaction.amount == amount
    assert transaction.memo == memo

    # Verify balances updated
    sender = account_repo.find_by_account_no(sender_account_no)
    assert sender.amount == 5000  # 10000 - 5000

    receiver = account_repo.find_by_account_no(receiver_account_no)
    assert receiver.amount == 5000  # 0 + 5000


def test_transfer_auto_creates_receiver_account(bank_service, account_repo, transaction_repo):
    """Auto-create receiver account if it doesn't exist."""
    # Create sender with initial balance
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, 10000)

    # Transfer to non-existent receiver
    receiver_id = "2222222222"
    amount = 5000
    transaction = bank_service.transfer(sender_id, receiver_id, amount, "Auto-create test")

    # Verify transaction was created
    assert transaction is not None
    assert transaction.status == "done"

    # Verify receiver account was auto-created
    receiver_account_no = bank_service._get_account_no(receiver_id)
    receiver = account_repo.find_by_account_no(receiver_account_no)
    assert receiver is not None
    assert receiver.amount == 5000


def test_transfer_sender_not_found(bank_service):
    """Should raise AccountNotFoundError when sender doesn't exist."""
    # Try to transfer from non-existent sender
    with pytest.raises(AccountNotFoundError) as exc_info:
        bank_service.transfer("9999999999", "2222222222", 100, "Test")

    # Verify the error message contains the account number
    assert "999999999" in str(exc_info.value)  # Last 9 digits


def test_transfer_same_account_raises_error(bank_service, account_repo):
    """Should raise InvalidTransferError when sender and receiver are the same."""
    # Create an account with balance
    user_id = "1234567890"
    bank_service.create_account(user_id, "Alice")
    account_no = bank_service._get_account_no(user_id)
    account_repo.update_amount(account_no, 1000)

    # Try to transfer to self
    with pytest.raises(InvalidTransferError):
        bank_service.transfer(user_id, user_id, 100, "Test")


def test_transfer_negative_amount_raises_error(bank_service, account_repo):
    """Should raise InvalidAmountError for negative amount."""
    # Create sender with balance
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, 1000)

    # Create receiver
    receiver_id = "2222222222"
    bank_service.create_account(receiver_id, "Bob")

    # Try to transfer negative amount
    with pytest.raises(InvalidAmountError):
        bank_service.transfer(sender_id, receiver_id, -100, "Test")


def test_transfer_zero_amount_raises_error(bank_service, account_repo):
    """Should raise InvalidAmountError for zero amount."""
    # Create sender with balance
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, 1000)

    # Create receiver
    receiver_id = "2222222222"
    bank_service.create_account(receiver_id, "Bob")

    # Try to transfer zero amount
    with pytest.raises(InvalidAmountError):
        bank_service.transfer(sender_id, receiver_id, 0, "Test")


def test_transfer_insufficient_balance(bank_service, account_repo):
    """Should raise InsufficientBalanceError when sender doesn't have enough balance."""
    # Create sender with small balance
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, 500)

    # Create receiver
    receiver_id = "2222222222"
    bank_service.create_account(receiver_id, "Bob")

    # Try to transfer more than available
    with pytest.raises(InsufficientBalanceError):
        bank_service.transfer(sender_id, receiver_id, 1000, "Test")


def test_transfer_when_balance_below_minimum(bank_service, account_repo):
    """Should raise InsufficientBalanceError when transfer would put balance below minimum."""
    # Create sender with balance at minimum (-1B)
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, -1_000_000_000)  # At minimum

    # Create receiver
    receiver_id = "2222222222"
    bank_service.create_account(receiver_id, "Bob")

    # Try to transfer (should fail - already at minimum)
    with pytest.raises(InsufficientBalanceError):
        bank_service.transfer(sender_id, receiver_id, 100, "Test")


def test_transfer_updates_both_accounts(bank_service, account_repo, transaction_repo):
    """Verify both sender and receiver balances are updated atomically."""
    # Create sender with initial balance
    sender_id = "1111111111"
    bank_service.create_account(sender_id, "Alice")
    sender_account_no = bank_service._get_account_no(sender_id)
    account_repo.update_amount(sender_account_no, 10000)

    # Create receiver
    receiver_id = "2222222222"
    bank_service.create_account(receiver_id, "Bob")
    receiver_account_no = bank_service._get_account_no(receiver_id)

    # Perform transfer
    amount = 5000
    bank_service.transfer(sender_id, receiver_id, amount, "Test")

    # Verify both balances updated
    sender = account_repo.find_by_account_no(sender_account_no)
    receiver = account_repo.find_by_account_no(receiver_account_no)

    assert sender.amount == 5000  # 10000 - 5000
    assert receiver.amount == 5000  # 0 + 5000
