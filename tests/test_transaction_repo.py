"""Tests for TransactionRepository."""

import sqlite3
import pytest
from datetime import datetime

from src.models.transaction import Transaction
from src.repositories.transaction_repo import TransactionRepository


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def transaction_repo(in_memory_db):
    """Create a TransactionRepository instance with a fresh database."""
    repo = TransactionRepository(in_memory_db)
    repo.create_table()
    return repo


def test_create_table(transaction_repo):
    """Verify Transactions table is created."""
    # Query sqlite_master to check if table exists
    cursor = transaction_repo._conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='Transactions'"
    )
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "Transactions"

    # Verify columns
    cursor.execute("PRAGMA table_info(Transactions)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert columns == {
        "TransactionID": "INTEGER",
        "Type": "TEXT",
        "Time": "TEXT",
        "Sender Account": "TEXT",
        "Receiver Account": "TEXT",
        "Status": "TEXT",
        "Amount": "INTEGER",
        "Operator": "TEXT",
        "Memo": "TEXT",
    }


def test_create_transaction(transaction_repo):
    """Create transaction, verify ID assigned."""
    txn = Transaction.create_pending(
        type="transfer",
        sender="123456789",
        receiver="987654321",
        amount=100,
        memo="Test transfer"
    )

    txn_id = transaction_repo.create(txn)

    # ID should be assigned
    assert txn_id == 1

    # Verify the transaction was created
    found = transaction_repo.find_by_id(1)
    assert found is not None
    assert found.id == 1
    assert found.type == "transfer"
    assert found.sender_account == "123456789"
    assert found.receiver_account == "987654321"
    assert found.status == "pending"
    assert found.amount == 100
    assert found.memo == "Test transfer"
    assert found.operator is None


def test_find_by_id_not_found(transaction_repo):
    """Should return None."""
    result = transaction_repo.find_by_id(999)
    assert result is None


def test_find_pending_transactions(transaction_repo):
    """Get only pending transactions."""
    # Create multiple transactions with different statuses
    txn1 = Transaction.create_pending("transfer", "111", "222", 100, "Memo 1")
    txn2 = Transaction.create_pending("deposit", "333", "333", 200, "Memo 2")
    txn3 = Transaction.create_pending("withdraw", "444", "444", 50, "Memo 3")

    id1 = transaction_repo.create(txn1)
    id2 = transaction_repo.create(txn2)
    id3 = transaction_repo.create(txn3)

    # Update one to 'done'
    transaction_repo.update_status(id1, "done", "admin_user")

    # Update one to 'denied'
    transaction_repo.update_status(id2, "denied", "admin_user")

    # Find pending transactions
    pending = transaction_repo.find_pending_transactions(limit=10)

    assert len(pending) == 1
    assert pending[0].id == id3
    assert pending[0].status == "pending"


def test_find_by_account(transaction_repo):
    """Get transactions where account is sender OR receiver."""
    # Create transactions for different accounts
    txn1 = Transaction.create_pending("transfer", "111", "222", 100, "A to B")
    txn2 = Transaction.create_pending("transfer", "333", "111", 200, "C to A")
    txn3 = Transaction.create_pending("transfer", "444", "555", 50, "D to E")
    txn4 = Transaction.create_pending("deposit", "111", "111", 300, "Deposit to A")

    id1 = transaction_repo.create(txn1)
    id2 = transaction_repo.create(txn2)
    id3 = transaction_repo.create(txn3)
    id4 = transaction_repo.create(txn4)

    # Mark one as denied (should be excluded)
    transaction_repo.update_status(id1, "denied", "admin_user")

    # Find transactions for account "111" (should get 2: id2 as receiver, id4 as sender/receiver)
    txns = transaction_repo.find_by_account("111", limit=10)

    assert len(txns) == 2
    txn_ids = {t.id for t in txns}
    assert txn_ids == {id2, id4}

    # Verify ordering (DESC by TransactionID)
    assert txns[0].id == id4  # Most recent
    assert txns[1].id == id2


def test_update_status(transaction_repo):
    """Update status and operator."""
    txn = Transaction.create_pending("transfer", "111", "222", 100, "Test")
    txn_id = transaction_repo.create(txn)

    # Update status to 'done' with operator
    transaction_repo.update_status(txn_id, "done", "admin_user")

    # Verify the update
    updated = transaction_repo.find_by_id(txn_id)
    assert updated is not None
    assert updated.status == "done"
    assert updated.operator == "admin_user"
    assert updated.type == "transfer"
    assert updated.amount == 100
