"""Account repository for database operations."""

import sqlite3

from src.models.account import Account
from src.models.exceptions import AccountAlreadyExistsError


class AccountRepository:
    """Repository for Account data access operations."""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize the repository with a database connection.

        Args:
            conn: SQLite database connection
        """
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def create_table(self) -> None:
        """Create the Accounts table if it doesn't exist."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Account TEXT UNIQUE,
                Name TEXT,
                Amount INTEGER,
                Pending INTEGER,
                Share INTEGER
            )
        """
        )
        self._conn.commit()

    def find_by_account_no(self, account_no: str) -> Account | None:
        """
        Find an account by account number.

        Args:
            account_no: The account number to search for

        Returns:
            Account object if found, None otherwise
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, Account, Name, Amount, Pending, Share FROM Accounts WHERE Account = ?",
            (account_no,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return Account(
            id=row["id"],
            account_no=row["Account"],
            name=row["Name"],
            amount=row["Amount"],
            pending=row["Pending"],
            share=row["Share"],
        )

    def create(self, account: Account) -> None:
        """
        Create a new account.

        Args:
            account: The Account object to create

        Raises:
            AccountAlreadyExistsError: If an account with the same account_no already exists
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO Accounts (Account, Name, Amount, Pending, Share)
                VALUES (?, ?, ?, ?, ?)
            """,
                (account.account_no, account.name, account.amount, account.pending, account.share),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise AccountAlreadyExistsError(f"Account {account.account_no} already exists")

    def exists(self, account_no: str) -> bool:
        """
        Check if an account exists.

        Args:
            account_no: The account number to check

        Returns:
            True if the account exists, False otherwise
        """
        cursor = self._conn.cursor()
        cursor.execute("SELECT 1 FROM Accounts WHERE Account = ?", (account_no,))
        return cursor.fetchone() is not None

    def update_pending(self, account_no: str, delta: int) -> None:
        """
        Update the pending balance by adding delta.

        Args:
            account_no: The account number to update
            delta: The amount to add (can be negative)
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE Accounts SET Pending = Pending + ? WHERE Account = ?",
            (delta, account_no),
        )
        self._conn.commit()

    def update_amount(self, account_no: str, delta: int) -> None:
        """
        Update the amount balance by adding delta.

        Args:
            account_no: The account number to update
            delta: The amount to add (can be negative)
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE Accounts SET Amount = Amount + ? WHERE Account = ?",
            (delta, account_no),
        )
        self._conn.commit()

    def update_pending_and_amount(
        self, account_no: str, pending_delta: int, amount_delta: int
    ) -> None:
        """
        Update both pending and amount balances atomically.

        This is useful for audit approval where pending decreases
        and amount increases simultaneously.

        Args:
            account_no: The account number to update
            pending_delta: The amount to add to pending (can be negative)
            amount_delta: The amount to add to amount (can be negative)
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE Accounts SET Pending = Pending + ?, Amount = Amount + ? WHERE Account = ?",
            (pending_delta, amount_delta, account_no),
        )
        self._conn.commit()
