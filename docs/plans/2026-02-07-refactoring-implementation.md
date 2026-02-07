# TeaBankBot Layered Architecture Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor TeaBankBot to use layered architecture (Cogs → Services → Repositories → Database) with improved code quality (type annotations, tests, config management).

**Architecture:** Introduce Service layer between Discord commands and SQLite, separate data access into Repositories, use dataclasses/models for type safety, and add comprehensive test coverage.

**Tech Stack:** Python 3.11, discord.py 2.6+, SQLite, pytest, pygsheets, python-dotenv

---

## Task 1: Create Directory Structure

**Files:**
- Create: `src/__init__.py`
- Create: `src/models/__init__.py`
- Create: `src/repositories/__init__.py`
- Create: `src/services/__init__.py`
- Create: `config/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/__init__.py`

**Step 1: Create all directories**

```bash
mkdir -p src models repositories services config tests/fixtures
```

**Step 2: Create __init__.py files**

```bash
touch src/__init__.py
touch src/models/__init__.py
touch src/repositories/__init__.py
touch src/services/__init__.py
touch config/__init__.py
touch tests/__init__.py
touch tests/fixtures/__init__.py
```

**Step 3: Verify structure**

Run: `tree src/ config/ tests/` or `find src/ config/ tests/ -name "__init__.py"`
Expected: All __init__.py files exist

**Step 4: Commit**

```bash
git add src/ config/ tests/
git commit -m "refactor: create directory structure for layered architecture"
```

---

## Task 2: Create Configuration Management

**Files:**
- Create: `config/settings.py`

**Step 1: Write the settings module**

```python
# config/settings.py
from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    """Application configuration loaded from environment variables."""

    # Discord
    discord_token: str
    discord_test_token: str

    # Database
    prod_db_path: str = 'teabank.db'
    test_db_path: str = 'testbank.db'

    # Google Sheets
    gs_credentials_path: str = './teabank-9ce129712f0c.json'
    prod_sheet_name: str = 'TeaBank'
    test_sheet_name: str = 'TestBank'

    # Business Rules
    max_deposit_amount: int = 1_000_000_000_000
    max_request_amount: int = 100_000_000_000
    max_transfer_amount: int = 1_000_000_000_000
    min_balance: int = -1_000_000_000

    # Audit
    audit_max_output: int = 20
    blocked_channel_ids: list[int] = field(default_factory=lambda: [854068518172229662])

    # Owner
    owner_id: int = 356096513828454411
    admin_role_name: str = '管理员'

    @classmethod
    def load(cls) -> 'Settings':
        """Load settings from environment variables."""
        return cls(
            discord_token=os.getenv('DISCORD_TOKEN', ''),
            discord_test_token=os.getenv('DISCORD_TOKEN_TEST', ''),
        )
```

**Step 2: Write test for settings**

```python
# tests/test_settings.py
import os
from config.settings import Settings

def test_settings_load():
    """Test that settings can be loaded with defaults."""
    os.environ['DISCORD_TOKEN'] = 'test_token'
    os.environ['DISCORD_TOKEN_TEST'] = 'test_token_test'

    settings = Settings.load()

    assert settings.discord_token == 'test_token'
    assert settings.prod_db_path == 'teabank.db'
    assert settings.max_deposit_amount == 1_000_000_000_000
    assert settings.audit_max_output == 20
    assert settings.blocked_channel_ids == [854068518172229662]

def test_settings_defaults():
    """Test default values for settings."""
    settings = Settings(discord_token='x', discord_test_token='y')

    assert settings.prod_db_path == 'teabank.db'
    assert settings.admin_role_name == '管理员'
    assert settings.min_balance == -1_000_000_000
```

**Step 3: Run tests**

Run: `pytest tests/test_settings.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add config/settings.py tests/test_settings.py
git commit -m "feat: add configuration management with Settings class"
```

---

## Task 3: Create Data Models and Exceptions

**Files:**
- Create: `src/models/exceptions.py`
- Create: `src/models/account.py`
- Create: `src/models/transaction.py`
- Create: `tests/test_models.py`

**Step 1: Write exceptions module**

```python
# src/models/exceptions.py
class BankError(Exception):
    """Base exception for all banking operations."""
    pass

class AccountNotFoundError(BankError):
    """Raised when an account is not found."""
    pass

class AccountAlreadyExistsError(BankError):
    """Raised when attempting to create a duplicate account."""
    pass

class InsufficientBalanceError(BankError):
    """Raised when an account has insufficient balance for an operation."""
    pass

class InvalidAmountError(BankError):
    """Raised when an amount is invalid (negative, zero, or exceeds limits)."""
    pass

class TransactionNotFoundError(BankError):
    """Raised when a transaction is not found."""
    pass

class InvalidTransactionStatusError(BankError):
    """Raised when attempting to modify a transaction with invalid status transition."""
    pass

class InvalidTransferError(BankError):
    """Raised when a transfer operation is invalid (e.g., transfer to self)."""
    pass

class UnauthorizedError(BankError):
    """Raised when a user is not authorized to perform an operation."""
    pass
```

**Step 2: Write account model**

```python
# src/models/account.py
from dataclasses import dataclass

@dataclass
class Account:
    """Bank account data model."""
    id: int
    account_no: str    # Account number (last 9 digits of user_id)
    name: str          # Account holder display name
    amount: int        # Confirmed balance
    pending: int       # Pending balance (awaiting audit)
    share: int         # Share amount (currently unused)

    @property
    def total_balance(self) -> int:
        """Total balance including pending funds."""
        return self.amount + self.pending
```

**Step 3: Write transaction model**

```python
# src/models/transaction.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Transaction:
    """Transaction record data model."""
    id: int | None     # None before database insert
    type: str          # deposit, withdraw, transfer, request, donate, admin-send
    time: str          # ISO format timestamp
    sender_account: str
    receiver_account: str
    status: str        # pending, done, denied
    amount: int
    operator: str | None
    memo: str

    @classmethod
    def create_pending(cls, type: str, sender: str, receiver: str, amount: int, memo: str) -> 'Transaction':
        """Create a new pending transaction with current timestamp."""
        now = datetime.now()
        return cls(
            id=None,
            type=type,
            time=now.strftime("%Y-%m-%d %H:%M:%S"),
            sender_account=sender,
            receiver_account=receiver,
            status='pending',
            amount=amount,
            operator=None,
            memo=memo
        )
```

**Step 4: Write tests for models**

```python
# tests/test_models.py
import pytest
from src.models.account import Account
from src.models.transaction import Transaction
from src.models.exceptions import *

def test_account_creation():
    account = Account(id=1, account_no='123456789', name='TestUser', amount=1000, pending=500, share=0)
    assert account.account_no == '123456789'
    assert account.total_balance == 1500

def test_transaction_create_pending():
    txn = Transaction.create_pending('deposit', '', '123456789', 1000, 'test')
    assert txn.id is None
    assert txn.status == 'pending'
    assert txn.type == 'deposit'
    assert txn.amount == 1000

def test_exceptions_hierarchy():
    assert issubclass(AccountNotFoundError, BankError)
    assert issubclass(InsufficientBalanceError, BankError)
    assert issubclass(InvalidAmountError, BankError)
```

**Step 5: Run tests**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add src/models/ tests/test_models.py
git commit -m "feat: add data models and custom exceptions"
```

---

## Task 4: Create AccountRepository

**Files:**
- Create: `src/repositories/account_repo.py`
- Create: `tests/test_account_repo.py`

**Step 1: Write failing tests for AccountRepository**

```python
# tests/test_account_repo.py
import pytest
import sqlite3
from src.repositories.account_repo import AccountRepository
from src.models.account import Account
from src.models.exceptions import AccountAlreadyExistsError

@pytest.fixture
def test_db():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(':memory:')
    repo = AccountRepository(conn)
    repo.create_table()
    yield repo
    conn.close()

def test_create_table(test_db):
    """Test that accounts table is created."""
    cursor = test_db._conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='Accounts'
    """)
    result = cursor.fetchone()
    assert result is not None

def test_create_account(test_db):
    """Test creating a new account."""
    account = Account(id=1, account_no='123456789', name='TestUser', amount=0, pending=0, share=0)
    test_db.create(account)

    found = test_db.find_by_account_no('123456789')
    assert found is not None
    assert found.name == 'TestUser'
    assert found.amount == 0

def test_create_duplicate_account(test_db):
    """Test creating duplicate account raises error."""
    account = Account(id=1, account_no='123456789', name='TestUser', amount=0, pending=0, share=0)
    test_db.create(account)

    with pytest.raises(AccountAlreadyExistsError):
        test_db.create(account)

def test_find_by_account_no_not_found(test_db):
    """Test finding non-existent account returns None."""
    result = test_db.find_by_account_no('999999999')
    assert result is None

def test_exists(test_db):
    """Test checking if account exists."""
    account = Account(id=1, account_no='123456789', name='TestUser', amount=0, pending=0, share=0)
    test_db.create(account)

    assert test_db.exists('123456789') is True
    assert test_db.exists('999999999') is False

def test_update_pending(test_db):
    """Test updating pending balance."""
    account = Account(id=1, account_no='123456789', name='TestUser', amount=0, pending=0, share=0)
    test_db.create(account)

    test_db.update_pending('123456789', 1000)

    found = test_db.find_by_account_no('123456789')
    assert found.pending == 1000
    assert found.amount == 0

def test_update_amount(test_db):
    """Test updating amount balance."""
    account = Account(id=1, account_no='123456789', name='TestUser', amount=0, pending=0, share=0)
    test_db.create(account)

    test_db.update_amount('123456789', 500)

    found = test_db.find_by_account_no('123456789')
    assert found.amount == 500
    assert found.pending == 0

def test_update_pending_and_amount(test_db):
    """Test updating both balances (for audit approval)."""
    account = Account(id=1, account_no='123456789', name='TestUser', amount=0, pending=0, share=0)
    test_db.create(account)

    test_db.update_pending('123456789', 1000)  # Deposit pending
    test_db.update_pending_and_amount('123456789', -1000, 1000)  # Approve: pending -1000, amount +1000

    found = test_db.find_by_account_no('123456789')
    assert found.amount == 1000
    assert found.pending == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_account_repo.py -v`
Expected: FAIL with "AccountRepository not defined"

**Step 3: Implement AccountRepository**

```python
# src/repositories/account_repo.py
import sqlite3
from src.models.account import Account
from src.models.exceptions import AccountAlreadyExistsError

class AccountRepository:
    """Repository for Account data access."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def create_table(self) -> None:
        """Create the Accounts table if it doesn't exist."""
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS "Accounts" (
                "id" INTEGER NOT NULL,
                "Account" TEXT NOT NULL UNIQUE,
                "Name" TEXT NOT NULL,
                "Amount" INTEGER,
                "Pending" INTEGER,
                "Share" INTEGER,
                PRIMARY KEY("id" AUTOINCREMENT)
            )
        ''')
        self._conn.commit()

    def find_by_account_no(self, account_no: str) -> Account | None:
        """Find an account by account number."""
        cursor = self._conn.execute(
            "SELECT * FROM Accounts WHERE Account = ?",
            (account_no,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Account(
            id=row['id'],
            account_no=row['Account'],
            name=row['Name'],
            amount=row['Amount'],
            pending=row['Pending'],
            share=row['Share']
        )

    def create(self, account: Account) -> None:
        """Create a new account."""
        try:
            self._conn.execute('''
                INSERT INTO Accounts ("Account", "Name", "Amount", "Pending", "Share")
                VALUES (?, ?, ?, ?, ?)
            ''', (account.account_no, account.name, account.amount, account.pending, account.share))
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise AccountAlreadyExistsError(f"Account {account.account_no} already exists")

    def exists(self, account_no: str) -> bool:
        """Check if an account exists."""
        cursor = self._conn.execute(
            "SELECT 1 FROM Accounts WHERE Account = ?",
            (account_no,)
        )
        return cursor.fetchone() is not None

    def update_pending(self, account_no: str, delta: int) -> None:
        """Update pending balance by adding delta."""
        self._conn.execute('''
            UPDATE Accounts SET Pending = Pending + ? WHERE Account = ?
        ''', (delta, account_no))
        self._conn.commit()

    def update_amount(self, account_no: str, delta: int) -> None:
        """Update amount balance by adding delta."""
        self._conn.execute('''
            UPDATE Accounts SET Amount = Amount + ? WHERE Account = ?
        ''', (delta, account_no))
        self._conn.commit()

    def update_pending_and_amount(self, account_no: str, pending_delta: int, amount_delta: int) -> None:
        """Update both pending and amount balances atomically."""
        self._conn.execute('''
            UPDATE Accounts SET Pending = Pending + ?, Amount = Amount + ? WHERE Account = ?
        ''', (pending_delta, amount_delta, account_no))
        self._conn.commit()
```

**Step 4: Run tests**

Run: `pytest tests/test_account_repo.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add src/repositories/account_repo.py tests/test_account_repo.py
git commit -m "feat: implement AccountRepository with tests"
```

---

## Task 5: Create TransactionRepository

**Files:**
- Create: `src/repositories/transaction_repo.py`
- Create: `tests/test_transaction_repo.py`

**Step 1: Write failing tests**

```python
# tests/test_transaction_repo.py
import pytest
import sqlite3
from src.repositories.transaction_repo import TransactionRepository
from src.models.transaction import Transaction

@pytest.fixture
def test_db():
    conn = sqlite3.connect(':memory:')
    repo = TransactionRepository(conn)
    repo.create_table()
    yield repo
    conn.close()

def test_create_table(test_db):
    cursor = test_db._conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='Transactions'
    """)
    assert cursor.fetchone() is not None

def test_create_transaction(test_db):
    txn = Transaction.create_pending('deposit', '', '123456789', 1000, 'test memo')
    txn_id = test_db.create(txn)

    assert txn_id == 1
    found = test_db.find_by_id(1)
    assert found is not None
    assert found.type == 'deposit'
    assert found.amount == 1000

def test_find_by_id_not_found(test_db):
    result = test_db.find_by_id(999)
    assert result is None

def test_find_pending_transactions(test_db):
    # Create multiple transactions
    test_db.create(Transaction.create_pending('deposit', '', '123', 100, ''))
    test_db.create(Transaction.create_pending('withdraw', '', '123', 50, ''))

    # Update one to 'done'
    test_db.update_status(1, 'done', 'admin')

    pending = test_db.find_pending_transactions(limit=10)
    assert len(pending) == 1
    assert pending[0].id == 2

def test_find_by_account(test_db):
    test_db.create(Transaction.create_pending('deposit', '', '123', 100, ''))
    test_db.create(Transaction.create_pending('withdraw', '123', '', 50, ''))

    txns = test_db.find_by_account('123', limit=10)
    # Should find transactions where account is sender OR receiver
    assert len(txns) == 2

def test_update_status(test_db):
    test_db.create(Transaction.create_pending('deposit', '', '123', 100, ''))

    test_db.update_status(1, 'done', 'admin')

    found = test_db.find_by_id(1)
    assert found.status == 'done'
    assert found.operator == 'admin'
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_transaction_repo.py -v`
Expected: FAIL with "TransactionRepository not defined"

**Step 3: Implement TransactionRepository**

```python
# src/repositories/transaction_repo.py
import sqlite3
from src.models.transaction import Transaction

class TransactionRepository:
    """Repository for Transaction data access."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def create_table(self) -> None:
        """Create the Transactions table if it doesn't exist."""
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS "Transactions" (
                "TransactionID" INTEGER NOT NULL UNIQUE,
                "Type" TEXT,
                "Time" TEXT,
                "Sender Account" TEXT,
                "Receiver Account" TEXT,
                "Status" TEXT,
                "Amount" INTEGER,
                "Operator" TEXT,
                "Memo" TEXT,
                PRIMARY KEY("TransactionID" AUTOINCREMENT)
            )
        ''')
        self._conn.commit()

    def create(self, txn: Transaction) -> int:
        """Create a new transaction and return its ID."""
        cursor = self._conn.execute('''
            INSERT INTO Transactions (
                "Type", "Time", "Sender Account", "Receiver Account",
                "Status", "Amount", "Memo", "Operator"
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (txn.type, txn.time, txn.sender_account, txn.receiver_account,
              txn.status, txn.amount, txn.memo, txn.operator))
        self._conn.commit()
        return cursor.lastrowid

    def find_by_id(self, txn_id: int) -> Transaction | None:
        """Find a transaction by ID."""
        cursor = self._conn.execute(
            "SELECT * FROM Transactions WHERE TransactionID = ?",
            (txn_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Transaction(
            id=row['TransactionID'],
            type=row['Type'],
            time=row['Time'],
            sender_account=row['Sender Account'],
            receiver_account=row['Receiver Account'],
            status=row['Status'],
            amount=row['Amount'],
            operator=row['Operator'],
            memo=row['Memo']
        )

    def find_pending_transactions(self, limit: int) -> list[Transaction]:
        """Find all pending transactions up to limit."""
        cursor = self._conn.execute('''
            SELECT * FROM Transactions
            WHERE Status = ?
            LIMIT ?
        ''', ('pending', limit))
        return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def find_by_account(self, account_no: str, limit: int) -> list[Transaction]:
        """Find transactions involving an account (sender or receiver)."""
        cursor = self._conn.execute('''
            SELECT * FROM Transactions
            WHERE ("Receiver Account" = ? OR "Sender Account" = ?) AND Status <> "denied"
            ORDER BY TransactionID DESC
            LIMIT ?
        ''', (account_no, account_no, limit))
        return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def update_status(self, txn_id: int, status: str, operator: str) -> None:
        """Update transaction status and operator."""
        self._conn.execute('''
            UPDATE Transactions
            SET Status = ?, Operator = ?
            WHERE TransactionID = ?
        ''', (status, operator, txn_id))
        self._conn.commit()

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        """Convert a database row to Transaction object."""
        return Transaction(
            id=row['TransactionID'],
            type=row['Type'],
            time=row['Time'],
            sender_account=row['Sender Account'],
            receiver_account=row['Receiver Account'],
            status=row['Status'],
            amount=row['Amount'],
            operator=row['Operator'],
            memo=row['Memo']
        )
```

**Step 4: Run tests**

Run: `pytest tests/test_transaction_repo.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/repositories/transaction_repo.py tests/test_transaction_repo.py
git commit -m "feat: implement TransactionRepository with tests"
```

---

## Task 6: Create BankService - Account Operations

**Files:**
- Create: `src/services/bank_service.py` (partial)
- Create: `tests/test_bank_service_account.py`

**Step 1: Write failing tests for account operations**

```python
# tests/test_bank_service_account.py
import pytest
import sqlite3
from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import AccountNotFoundError, AccountAlreadyExistsError

@pytest.fixture
def bank_service():
    conn = sqlite3.connect(':memory:')
    account_repo = AccountRepository(conn)
    transaction_repo = TransactionRepository(conn)
    account_repo.create_table()
    transaction_repo.create_table()
    return BankService(account_repo, transaction_repo)

def test_create_account_success(bank_service):
    account = bank_service.create_account('123456789', 'TestUser')
    assert account.account_no == '123456789'
    assert account.name == 'TestUser'
    assert account.amount == 0
    assert account.pending == 0

def test_create_duplicate_account_raises_error(bank_service):
    bank_service.create_account('123456789', 'TestUser')

    with pytest.raises(AccountAlreadyExistsError):
        bank_service.create_account('123456789', 'AnotherUser')

def test_get_balance_success(bank_service):
    bank_service.create_account('123456789', 'TestUser')
    balance = bank_service.get_balance('123456789')
    assert balance == (0, 0)

def test_get_balance_account_not_found(bank_service):
    with pytest.raises(AccountNotFoundError):
        bank_service.get_balance('999999999')

def test_account_no_truncated_from_user_id(bank_service):
    account = bank_service.create_account('9876543210987654321', 'TestUser')
    assert account.account_no == '987654321'  # Last 9 digits
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_bank_service_account.py -v`
Expected: FAIL with "BankService not defined"

**Step 3: Implement BankService (account operations only)**

```python
# src/services/bank_service.py
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.account import Account
from src.models.transaction import Transaction
from src.models.exceptions import (
    AccountNotFoundError,
    AccountAlreadyExistsError,
    InsufficientBalanceError,
    InvalidAmountError,
    TransactionNotFoundError,
    InvalidTransferError
)

class BankService:
    """Core banking business logic."""

    def __init__(
        self,
        account_repo: AccountRepository,
        transaction_repo: TransactionRepository,
        max_deposit_amount: int = 1_000_000_000_000,
        max_request_amount: int = 100_000_000_000,
        max_transfer_amount: int = 1_000_000_000_000,
        min_balance: int = -1_000_000_000
    ):
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo
        self._max_deposit_amount = max_deposit_amount
        self._max_request_amount = max_request_amount
        self._max_transfer_amount = max_transfer_amount
        self._min_balance = min_balance

    def _get_account_no(self, user_id: str) -> str:
        """Extract account number (last 9 digits) from user ID."""
        return str(user_id)[-9:]

    def _get_or_create_account(self, account_no: str, name: str) -> Account:
        """Get existing account or create new one."""
        account = self._account_repo.find_by_account_no(account_no)
        if account is None:
            account = Account(
                id=0,  # Will be set by database
                account_no=account_no,
                name=name,
                amount=0,
                pending=0,
                share=0
            )
            self._account_repo.create(account)
            account = self._account_repo.find_by_account_no(account_no)
        return account

    # ========== Account Operations ==========

    def create_account(self, user_id: str, name: str) -> Account:
        """Create a new bank account."""
        account_no = self._get_account_no(user_id)

        if self._account_repo.exists(account_no):
            raise AccountAlreadyExistsError(f"Account {account_no} already exists")

        account = Account(
            id=0,
            account_no=account_no,
            name=name,
            amount=0,
            pending=0,
            share=0
        )
        self._account_repo.create(account)
        return self._account_repo.find_by_account_no(account_no)

    def get_balance(self, user_id: str) -> tuple[int, int]:
        """Get account balance (amount, pending)."""
        account_no = self._get_account_no(user_id)
        account = self._account_repo.find_by_account_no(account_no)

        if account is None:
            raise AccountNotFoundError(f"Account {account_no} not found")

        return (account.amount, account.pending)
```

**Step 4: Run tests**

Run: `pytest tests/test_bank_service_account.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/services/bank_service.py tests/test_bank_service_account.py
git commit -m "feat: implement BankService account operations with tests"
```

---

## Task 7: Create BankService - Deposit Operations

**Files:**
- Modify: `src/services/bank_service.py`
- Create: `tests/test_bank_service_deposit.py`

**Step 1: Write failing tests for deposit**

```python
# tests/test_bank_service_deposit.py
import pytest
import sqlite3
from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import AccountNotFoundError, InvalidAmountError

@pytest.fixture
def bank_service():
    conn = sqlite3.connect(':memory:')
    account_repo = AccountRepository(conn)
    transaction_repo = TransactionRepository(conn)
    account_repo.create_table()
    transaction_repo.create_table()
    service = BankService(account_repo, transaction_repo)
    service.create_account('123456789', 'TestUser')
    return service

def test_deposit_success(bank_service):
    txn = bank_service.deposit('123456789', 1000, 'game earnings')

    assert txn.type == 'deposit'
    assert txn.status == 'pending'
    assert txn.amount == 1000
    assert txn.memo == 'game earnings'

def test_deposit_account_not_found(bank_service):
    with pytest.raises(AccountNotFoundError):
        bank_service.deposit('999999999', 1000, 'test')

def test_deposit_negative_amount_raises_error(bank_service):
    with pytest.raises(InvalidAmountError) as exc:
        bank_service.deposit('123456789', -100, 'test')
    assert 'negative' in str(exc.value).lower()

def test_deposit_zero_amount_raises_error(bank_service):
    with pytest.raises(InvalidAmountError):
        bank_service.deposit('123456789', 0, 'test')

def test_deposit_exceeds_max_amount(bank_service):
    with pytest.raises(InvalidAmountError):
        bank_service.deposit('123456789', 1_000_000_000_001, 'test')

def test_deposit_max_allowed_amount(bank_service):
    txn = bank_service.deposit('123456789', 1_000_000_000_000, 'max deposit')
    assert txn.amount == 1_000_000_000_000

def test_deposit_minimum_amount(bank_service):
    txn = bank_service.deposit('123456789', 1, 'micro deposit')
    assert txn.amount == 1

def test_deposit_with_empty_memo(bank_service):
    txn = bank_service.deposit('123456789', 1000, '')
    assert txn.memo == ''

def test_deposit_increases_pending_not_amount(bank_service):
    bank_service.deposit('123456789', 1000, 'test')
    balance = bank_service.get_balance('123456789')
    assert balance[0] == 0      # amount unchanged
    assert balance[1] == 1000   # pending increased
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_bank_service_deposit.py -v`
Expected: FAIL with "deposit method not found"

**Step 3: Add deposit method to BankService**

Add to `src/services/bank_service.py` after the account operations:

```python
    # ========== Deposit Operations ==========

    def deposit(self, user_id: str, amount: int, memo: str) -> Transaction:
        """Deposit funds into an account (creates pending transaction)."""
        account_no = self._get_account_no(user_id)

        # Validate account exists
        if not self._account_repo.exists(account_no):
            raise AccountNotFoundError(f"Account {account_no} not found")

        # Validate amount
        if amount <= 0:
            raise InvalidAmountError("Deposit amount must be positive")
        if amount > self._max_deposit_amount:
            raise InvalidAmountError(f"Deposit exceeds maximum of {self._max_deposit_amount}")

        # Create pending transaction
        txn = Transaction.create_pending('deposit', '', account_no, amount, memo)
        txn_id = self._transaction_repo.create(txn)

        # Update pending balance
        self._account_repo.update_pending(account_no, amount)

        txn.id = txn_id
        return txn
```

**Step 4: Run tests**

Run: `pytest tests/test_bank_service_deposit.py -v`
Expected: PASS (9 tests)

**Step 5: Commit**

```bash
git add src/services/bank_service.py tests/test_bank_service_deposit.py
git commit -m "feat: implement BankService deposit with tests"
```

---

## Task 8: Create BankService - Withdraw Operations

**Files:**
- Modify: `src/services/bank_service.py`
- Create: `tests/test_bank_service_withdraw.py`

**Step 1: Write failing tests for withdraw**

```python
# tests/test_bank_service_withdraw.py
import pytest
import sqlite3
from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import AccountNotFoundError, InsufficientBalanceError, InvalidAmountError

@pytest.fixture
def bank_service():
    conn = sqlite3.connect(':memory:')
    account_repo = AccountRepository(conn)
    transaction_repo = TransactionRepository(conn)
    account_repo.create_table()
    transaction_repo.create_table()
    service = BankService(account_repo, transaction_repo)
    return service

@pytest.fixture
def funded_account(bank_service):
    bank_service.create_account('123456789', 'TestUser')
    bank_service.deposit('123456789', 10000, 'initial')
    bank_service.approve_transaction(1, 'system')  # amount=10000, pending=0
    return bank_service

def test_withdraw_success(funded_account):
    txn = funded_account.withdraw('123456789', 5000, 'need cash')
    assert txn.status == 'pending'
    assert txn.amount == 5000

def test_withdraw_account_not_found(bank_service):
    with pytest.raises(AccountNotFoundError):
        bank_service.withdraw('999999999', 1000, 'test')

def test_withdraw_negative_amount_raises_error(bank_service):
    bank_service.create_account('123456789', 'TestUser')
    with pytest.raises(InvalidAmountError):
        bank_service.withdraw('123456789', -100, 'test')

def test_withdraw_exceeds_max_amount(bank_service):
    bank_service.create_account('123456789', 'TestUser')
    with pytest.raises(InvalidAmountError):
        bank_service.withdraw('123456789', 1_000_000_000_001, 'test')

def test_withdraw_insufficient_balance(funded_account):
    with pytest.raises(InsufficientBalanceError):
        funded_account.withdraw('123456789', 20000, 'test')

def test_withdraw_exact_balance(funded_account):
    txn = funded_account.withdraw('123456789', 10000, 'all in')
    assert txn.amount == 10000

def test_withdraw_with_pending_included(bank_service):
    bank_service.create_account('123456789', 'TestUser')
    bank_service.deposit('123456789', 1000, 'test1')  # pending 1000
    bank_service.deposit('123456789', 1000, 'test2')  # pending 2000
    txn = bank_service.withdraw('123456789', 2000, 'test')
    assert txn.status == 'pending'

def test_withdraw_decreases_pending(funded_account):
    funded_account.withdraw('123456789', 3000, 'test')
    balance = funded_account.get_balance('123456789')
    assert balance[0] == 10000   # amount unchanged
    assert balance[1] == -3000   # pending decreased
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_bank_service_withdraw.py -v`
Expected: FAIL with "withdraw method not found"

**Step 3: Add withdraw and approve methods to BankService**

Add to `src/services/bank_service.py`:

```python
    # ========== Withdraw Operations ==========

    def withdraw(self, user_id: str, amount: int, memo: str) -> Transaction:
        """Withdraw funds from an account (creates pending transaction)."""
        account_no = self._get_account_no(user_id)

        # Validate account exists
        if not self._account_repo.exists(account_no):
            raise AccountNotFoundError(f"Account {account_no} not found")

        # Validate amount
        if amount <= 0:
            raise InvalidAmountError("Withdrawal amount must be positive")
        if amount > self._max_deposit_amount:
            raise InvalidAmountError(f"Withdrawal exceeds maximum of {self._max_deposit_amount}")

        # Check balance
        account = self._account_repo.find_by_account_no(account_no)
        if account.amount + account.pending < amount:
            raise InsufficientBalanceError(f"Insufficient balance (amount + pending = {account.amount + account.pending})")

        # Create pending transaction
        txn = Transaction.create_pending('withdraw', account_no, '', amount, memo)
        txn_id = self._transaction_repo.create(txn)

        # Update pending balance
        self._account_repo.update_pending(account_no, -amount)

        txn.id = txn_id
        return txn

    # ========== Audit Operations ==========

    def approve_transaction(self, txn_id: int, operator: str) -> None:
        """Approve a pending transaction."""
        txn = self._transaction_repo.find_by_id(txn_id)
        if txn is None:
            raise TransactionNotFoundError(f"Transaction {txn_id} not found")

        if txn.status != 'pending':
            raise InvalidTransactionStatusError(f"Transaction is not pending (status: {txn.status})")

        receiver_account = txn.receiver_account

        # Determine amount direction based on transaction type
        if txn.type in ('deposit', 'request'):
            pending_delta = -txn.amount
            amount_delta = txn.amount
        elif txn.type in ('withdraw', 'donate'):
            pending_delta = txn.amount  # reverse the pending delta
            amount_delta = -txn.amount
        else:
            raise InvalidTransactionStatusError(f"Cannot approve transaction type: {txn.type}")

        # Update account
        self._account_repo.update_pending_and_amount(receiver_account, pending_delta, amount_delta)

        # Update transaction status
        self._transaction_repo.update_status(txn_id, 'done', operator)
```

**Step 4: Run tests**

Run: `pytest tests/test_bank_service_withdraw.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add src/services/bank_service.py tests/test_bank_service_withdraw.py
git commit -m "feat: implement BankService withdraw with tests"
```

---

## Task 9: Create BankService - Transfer Operations

**Files:**
- Modify: `src/services/bank_service.py`
- Create: `tests/test_bank_service_transfer.py`

**Step 1: Write failing tests for transfer**

```python
# tests/test_bank_service_transfer.py
import pytest
import sqlite3
from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import AccountNotFoundError, InsufficientBalanceError, InvalidAmountError, InvalidTransferError

@pytest.fixture
def bank_service():
    conn = sqlite3.connect(':memory:')
    account_repo = AccountRepository(conn)
    transaction_repo = TransactionRepository(conn)
    account_repo.create_table()
    transaction_repo.create_table()
    service = BankService(account_repo, transaction_repo)
    service.create_account('111111111', 'Sender')
    service.create_account('222222222', 'Receiver')
    return service

@pytest.fixture
def funded_transfer(bank_service):
    bank_service.deposit('111111111', 10000, 'initial')
    bank_service.approve_transaction(1, 'system')
    return bank_service

def test_transfer_success(funded_transfer):
    txn = funded_transfer.transfer('111111111', '222222222', 5000, 'payment')
    assert txn.type == 'transfer'
    assert txn.status == 'done'
    assert txn.amount == 5000

def test_transfer_auto_creates_receiver_account(bank_service):
    bank_service.deposit('111111111', 10000, 'initial')
    bank_service.approve_transaction(1, 'system')
    bank_service.transfer('111111111', '999999999', 5000, 'test')
    receiver_balance = bank_service.get_balance('999999999')
    assert receiver_balance == (5000, 0)

def test_transfer_sender_not_found(bank_service):
    with pytest.raises(AccountNotFoundError):
        bank_service.transfer('999999999', '111111111', 1000, 'test')

def test_transfer_same_account_raises_error(bank_service):
    with pytest.raises(InvalidTransferError):
        bank_service.transfer('111111111', '111111111', 1000, 'test')

def test_transfer_negative_amount_raises_error(bank_service):
    with pytest.raises(InvalidAmountError):
        bank_service.transfer('111111111', '222222222', -100, 'test')

def test_transfer_insufficient_balance(bank_service):
    bank_service.deposit('111111111', 1000, 'initial')
    bank_service.approve_transaction(1, 'system')
    with pytest.raises(InsufficientBalanceError):
        bank_service.transfer('111111111', '222222222', 2000, 'test')

def test_transfer_when_balance_below_minimum(bank_service):
    # Set up account with very low balance
    bank_service.deposit('111111111', 100, 'initial')
    bank_service.approve_transaction(1, 'system')
    # Manually set amount to below minimum
    bank_service._account_repo.update_amount('111111111', -2_000_000_000)
    with pytest.raises(InsufficientBalanceError):
        bank_service.transfer('111111111', '222222222', 1000, 'test')

def test_transfer_updates_both_accounts(funded_transfer):
    funded_transfer.transfer('111111111', '222222222', 5000, 'test')
    sender_balance = funded_transfer.get_balance('111111111')
    receiver_balance = funded_transfer.get_balance('222222222')
    assert sender_balance == (5000, 0)
    assert receiver_balance == (5000, 0)
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_bank_service_transfer.py -v`
Expected: FAIL with "transfer method not found"

**Step 3: Add transfer method to BankService**

Add to `src/services/bank_service.py`:

```python
    # ========== Transfer Operations ==========

    def transfer(self, from_user: str, to_user: str, amount: int, memo: str) -> Transaction:
        """Transfer funds from one user to another (immediate, no approval needed)."""
        from_account_no = self._get_account_no(from_user)
        to_account_no = self._get_account_no(to_user)

        # Validate accounts
        if not self._account_repo.exists(from_account_no):
            raise AccountNotFoundError(f"Sender account {from_account_no} not found")

        # Auto-create receiver account if needed
        if not self._account_repo.exists(to_account_no):
            to_name = to_user  # Will be updated by caller if needed
            self.create_account(to_user, to_name)

        # Validate transfer
        if from_account_no == to_account_no:
            raise InvalidTransferError("Cannot transfer to same account")

        if amount <= 0:
            raise InvalidAmountError("Transfer amount must be positive")

        if amount > self._max_transfer_amount:
            raise InvalidAmountError(f"Transfer exceeds maximum of {self._max_transfer_amount}")

        # Check sender balance
        sender = self._account_repo.find_by_account_no(from_account_no)
        if sender.amount < amount:
            raise InsufficientBalanceError(f"Insufficient balance (amount = {sender.amount})")

        if sender.amount < self._min_balance:
            raise InsufficientBalanceError(f"Account below minimum balance (min = {self._min_balance})")

        # Get receiver name
        receiver = self._account_repo.find_by_account_no(to_account_no)

        # Update balances
        self._account_repo.update_amount(from_account_no, -amount)
        self._account_repo.update_amount(to_account_no, amount)

        # Create completed transaction
        txn = Transaction.create_pending('transfer', from_account_no, to_account_no, amount, memo)
        txn.status = 'done'
        txn_id = self._transaction_repo.create(txn)
        txn.id = txn_id
        return txn
```

**Step 4: Run tests**

Run: `pytest tests/test_bank_service_transfer.py -v`
Expected: PASS (9 tests)

**Step 5: Commit**

```bash
git add src/services/bank_service.py tests/test_bank_service_transfer.py
git commit -m "feat: implement BankService transfer with tests"
```

---

## Task 10: Create BankService - Request/Donate/Deny/PullTransactions

**Files:**
- Modify: `src/services/bank_service.py`
- Create: `tests/test_bank_service_remaining.py`

**Step 1: Write failing tests for remaining operations**

```python
# tests/test_bank_service_remaining.py
import pytest
import sqlite3
from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import AccountNotFoundError, InsufficientBalanceError, InvalidAmountError, TransactionNotFoundError

@pytest.fixture
def bank_service():
    conn = sqlite3.connect(':memory:')
    account_repo = AccountRepository(conn)
    transaction_repo = TransactionRepository(conn)
    account_repo.create_table()
    transaction_repo.create_table()
    service = BankService(account_repo, transaction_repo)
    service.create_account('123456789', 'User')
    return service

# Request tests
def test_request_success(bank_service):
    txn = bank_service.request('123456789', 5000, 'corp purchase')
    assert txn.type == 'request'
    assert txn.status == 'pending'

def test_request_exceeds_max_limit(bank_service):
    with pytest.raises(InvalidAmountError):
        bank_service.request('123456789', 100_000_000_001, 'test')

# Donate tests
def test_donate_success(bank_service):
    bank_service.deposit('123456789', 10000, 'test')
    txn = bank_service.donate('123456789', 5000, 'donation')
    balance = bank_service.get_balance('123456789')
    assert balance[1] == 5000  # pending decreased from 10000 to 5000

def test_donate_exceeds_total_balance(bank_service):
    bank_service.deposit('123456789', 1000, 'test')
    with pytest.raises(InsufficientBalanceError):
        bank_service.donate('123456789', 5000, 'test')

# Deny tests
def test_deny_transaction_reverts_pending(bank_service):
    bank_service.deposit('123456789', 1000, 'test')
    bank_service.deny_transaction(1, 'admin')
    balance = bank_service.get_balance('123456789')
    assert balance == (0, 0)

def test_deny_nonexistent_transaction_raises_error(bank_service):
    with pytest.raises(TransactionNotFoundError):
        bank_service.deny_transaction(999, 'admin')

# PullTransactions tests
def test_pull_recent_transactions(bank_service):
    bank_service.deposit('123456789', 1000, 'test1')
    bank_service.deposit('123456789', 2000, 'test2')
    bank_service.deposit('123456789', 3000, 'test3')
    txns = bank_service.pull_transactions('123456789', 2)
    assert len(txns) == 2
    assert txns[0].amount == 2000
    assert txns[1].amount == 3000

def test_pull_transactions_excludes_denied(bank_service):
    bank_service.deposit('123456789', 1000, 'test1')
    bank_service.deny_transaction(1, 'admin')
    bank_service.deposit('123456789', 2000, 'test2')
    txns = bank_service.pull_transactions('123456789', 10)
    assert len(txns) == 1
    assert txns[0].amount == 2000

def test_get_pending_transactions(bank_service):
    bank_service.deposit('123456789', 1000, 'test')
    bank_service.deposit('123456789', 2000, 'test')
    pending = bank_service.get_pending_transactions(limit=10)
    assert len(pending) == 2
```

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_bank_service_remaining.py -v`
Expected: FAIL with multiple methods not found

**Step 3: Add remaining methods to BankService**

Add to `src/services/bank_service.py`:

```python
    # ========== Request Operations ==========

    def request(self, user_id: str, amount: int, memo: str) -> Transaction:
        """Request funds from corp (creates pending transaction)."""
        account_no = self._get_account_no(user_id)

        if not self._account_repo.exists(account_no):
            raise AccountNotFoundError(f"Account {account_no} not found")

        if amount <= 0:
            raise InvalidAmountError("Request amount must be positive")
        if amount > self._max_request_amount:
            raise InvalidAmountError(f"Request exceeds maximum of {self._max_request_amount}")

        txn = Transaction.create_pending('request', '', account_no, amount, memo)
        txn_id = self._transaction_repo.create(txn)
        self._account_repo.update_pending(account_no, amount)

        txn.id = txn_id
        return txn

    # ========== Donate Operations ==========

    def donate(self, user_id: str, amount: int, memo: str) -> Transaction:
        """Donate funds to corp (decreases pending)."""
        account_no = self._get_account_no(user_id)

        if not self._account_repo.exists(account_no):
            raise AccountNotFoundError(f"Account {account_no} not found")

        if amount <= 0:
            raise InvalidAmountError("Donation amount must be positive")
        if amount > self._max_deposit_amount:
            raise InvalidAmountError(f"Donation exceeds maximum of {self._max_deposit_amount}")

        account = self._account_repo.find_by_account_no(account_no)
        if account.amount + account.pending < amount:
            raise InsufficientBalanceError(f"Insufficient balance (total = {account.amount + account.pending})")

        txn = Transaction.create_pending('donate', account_no, '', amount, memo)
        txn_id = self._transaction_repo.create(txn)
        self._account_repo.update_pending(account_no, -amount)

        txn.id = txn_id
        return txn

    # ========== Deny Operations ==========

    def deny_transaction(self, txn_id: int, operator: str) -> None:
        """Deny a pending transaction."""
        txn = self._transaction_repo.find_by_id(txn_id)
        if txn is None:
            raise TransactionNotFoundError(f"Transaction {txn_id} not found")

        if txn.status != 'pending':
            raise InvalidTransactionStatusError(f"Transaction is not pending (status: {txn.status})")

        receiver_account = txn.receiver_account

        # Revert pending based on transaction type
        if txn.type in ('deposit', 'request'):
            pending_delta = -txn.amount
        elif txn.type in ('withdraw', 'donate'):
            pending_delta = txn.amount  # reverse the pending delta
        else:
            raise InvalidTransactionStatusError(f"Cannot deny transaction type: {txn.type}")

        self._account_repo.update_pending(receiver_account, pending_delta)
        self._transaction_repo.update_status(txn_id, 'denied', operator)

    # ========== Query Operations ==========

    def pull_transactions(self, user_id: str, n: int) -> list[Transaction]:
        """Get recent N transactions for a user."""
        account_no = self._get_account_no(user_id)
        return self._transaction_repo.find_by_account(account_no, n)

    def get_pending_transactions(self, limit: int = 20) -> list[Transaction]:
        """Get all pending transactions up to limit."""
        return self._transaction_repo.find_pending_transactions(limit)
```

**Step 4: Run tests**

Run: `pytest tests/test_bank_service_remaining.py -v`
Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add src/services/bank_service.py tests/test_bank_service_remaining.py
git commit -m "feat: implement BankService remaining operations with tests"
```

---

## Task 11: Create requirements.txt

**Files:**
- Create: `requirements.txt`

**Step 1: Write requirements.txt**

```
discord.py>=2.3.0
python-dotenv>=1.0.0
pygsheets>=2.0.0
tabulate>=0.9.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

**Step 2: Verify install works**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add requirements.txt with project dependencies"
```

---

## Task 12: Refactor Cogs Bank Commands

**Files:**
- Modify: `cogs/bankcmd.py`
- Create: `cogs/__init__.py`

**Step 1: Create cogs __init__.py**

```python
# cogs/__init__.py
```

**Step 2: Refactor bankcmd.py to use BankService**

The cog will now only handle Discord interaction, delegating business logic to BankService. Here's the key changes:

```python
# cogs/bankcmd.py (header imports)
import discord
import asyncio
import itertools
from tabulate import tabulate
from discord.ext import commands
from src.services.bank_service import BankService
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository
from src.models.exceptions import BankError, AccountNotFoundError, InsufficientBalanceError, InvalidAmountError
import sqlite3

def check_admin_role(ctx):
    return (ctx.author.id == ctx.bot.owner_id) or ('管理员' in [role.name for role in ctx.author.roles])

class bankcmd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize service layer
        settings = bot.settings
        db_path = settings.test_db_path if settings.is_test else settings.prod_db_path
        conn = sqlite3.connect(db_path)
        self.bank_service = BankService(
            AccountRepository(conn),
            TransactionRepository(conn),
            max_deposit_amount=settings.max_deposit_amount,
            max_request_amount=settings.max_request_amount,
            max_transfer_amount=settings.max_transfer_amount,
            min_balance=settings.min_balance
        )

    # Keep existing _toggle_number and _reply methods
    # Update commands to use self.bank_service instead of self.bot.bank

    @commands.command(name='register', help='$register 新建账户')
    async def register(self, ctx):
        user = ctx.message.author
        try:
            self.bank_service.create_account(str(user.id), user.display_name)
            await ctx.send('```Congratulations! Your account is created!```')
        except BankError as e:
            await ctx.send(f'```{e}```')

    @commands.command(name='deposit', help='$deposit n memo(Optional) 存钱进账户')
    async def deposit(self, ctx, n: int, *args):
        user = ctx.message.author
        memo = ' '.join(args).lstrip('<').rstrip('>')
        try:
            self.bank_service.deposit(str(user.id), n, memo)
            premsg = f'```{user.display_name} has deposited {{}} isk```'
            await self._reply(ctx, premsg, n)
        except BankError as e:
            await ctx.send(f'```{e}```')

    # Similar pattern for other commands...
    # withdraw, send, request, donate, check, record, recall, audit, admin-send

def setup(bot):
    bot.add_cog(bankcmd(bot))
    print('bankcmd is loaded')
```

**Step 3: Update bot initialization**

Modify `teabot.py` and `testbot.py` to pass settings:

```python
# teabot.py
import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from config.settings import Settings

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

load_dotenv()
settings = Settings.load()
settings.is_test = False

extensions = ("cogs.bankcmd",)

intents = discord.Intents.default()
intents.members = True

class BankBot(commands.Bot):
    def __init__(self, settings: Settings):
        super().__init__(
            command_prefix='$',
            owner_id=settings.owner_id,
            intents=intents
        )
        self.settings = settings
        for extension in extensions:
            self.load_extension(extension)

TeaBot = BankBot(settings)
TeaBot.run(settings.discord_token)
```

**Step 4: Test bot starts (manual check)**

Run: `python teabot.py`
Expected: Bot connects to Discord (will fail without valid token but should initialize)

**Step 5: Commit**

```bash
git add cogs/__init__.py cogs/bankcmd.py teabot.py testbot.py
git commit -m "refactor: update cogs to use BankService layer"
```

---

## Task 13: Run All Tests and Verify

**Step 1: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass (50+ tests)

**Step 2: Generate coverage report**

Run: `pytest tests/ --cov=src --cov-report=html`

Open `htmlcov/index.html` to verify good coverage

**Step 3: Final commit if needed**

```bash
git add .
git commit -m "test: ensure all tests pass with good coverage"
```

---

## Completion Checklist

- [ ] All tasks completed
- [ ] All tests passing
- [ ] Code follows TDD principles
- [ ] Type annotations added
- [ ] Documentation updated
- [ ] Git history clean with frequent commits

---

## Next Steps

After implementation is complete:

1. **Test in development environment** - Verify Discord bot works correctly
2. **Update CLAUDE.md** - Document new architecture
3. **Create migration guide** - If upgrading existing database
4. **Consider adding**:
   - Google Sheets backup integration in service layer
   - Admin operations (admin-send)
   - More comprehensive integration tests
