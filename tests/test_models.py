"""Tests for data models and exceptions."""

import pytest

from src.models.account import Account
from src.models.transaction import Transaction
from src.models.exceptions import (
    BankError,
    AccountNotFoundError,
    AccountAlreadyExistsError,
    InsufficientBalanceError,
    InvalidAmountError,
    TransactionNotFoundError,
    InvalidTransactionStatusError,
    InvalidTransferError,
    UnauthorizedError,
)


def test_account_creation():
    """Test creating an Account and verifying its fields and total_balance property."""
    account = Account(
        id=1,
        account_no="12345",
        name="Alice",
        amount=100.0,
        pending=50.0,
        share=0.0,
    )

    assert account.id == 1
    assert account.account_no == "12345"
    assert account.name == "Alice"
    assert account.amount == 100.0
    assert account.pending == 50.0
    assert account.share == 0.0
    assert account.total_balance == 150.0


def test_transaction_create_pending():
    """Test creating a pending transaction using the create_pending class method."""
    transaction = Transaction.create_pending(
        type="transfer",
        sender="12345",
        receiver="67890",
        amount=50,
        memo="Test transfer",
    )

    assert transaction.id is None
    assert transaction.type == "transfer"
    assert transaction.sender_account == "12345"
    assert transaction.receiver_account == "67890"
    assert transaction.amount == 50
    assert transaction.status == "pending"
    assert transaction.operator is None
    assert transaction.memo == "Test transfer"
    assert transaction.time is not None


def test_exceptions_hierarchy():
    """Test that all custom exceptions inherit from BankError."""
    assert issubclass(AccountNotFoundError, BankError)
    assert issubclass(AccountAlreadyExistsError, BankError)
    assert issubclass(InsufficientBalanceError, BankError)
    assert issubclass(InvalidAmountError, BankError)
    assert issubclass(TransactionNotFoundError, BankError)
    assert issubclass(InvalidTransactionStatusError, BankError)
    assert issubclass(InvalidTransferError, BankError)
    assert issubclass(UnauthorizedError, BankError)

    # Also verify they can be instantiated and caught
    errors = [
        AccountNotFoundError(),
        AccountAlreadyExistsError(),
        InsufficientBalanceError(),
        InvalidAmountError(),
        TransactionNotFoundError(),
        InvalidTransactionStatusError(),
        InvalidTransferError(),
        UnauthorizedError(),
    ]

    for error in errors:
        assert isinstance(error, BankError)
