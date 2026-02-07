"""Transaction repository for database operations."""

import sqlite3
from datetime import datetime

from src.models.transaction import Transaction


class TransactionRepository:
    """Repository for Transaction data access operations."""

    def __init__(self, conn: sqlite3.Connection):
        """
        Initialize the repository with a database connection.

        Args:
            conn: SQLite database connection
        """
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def create_table(self) -> None:
        """Create the Transactions table if it doesn't exist."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS Transactions (
                TransactionID INTEGER PRIMARY KEY AUTOINCREMENT,
                Type TEXT,
                Time TEXT,
                "Sender Account" TEXT,
                "Receiver Account" TEXT,
                Status TEXT,
                Amount INTEGER,
                Operator TEXT,
                Memo TEXT
            )
        """
        )
        self._conn.commit()

    def create(self, txn: Transaction) -> int:
        """
        Create a new transaction.

        Args:
            txn: The Transaction object to create

        Returns:
            The ID of the newly created transaction
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO Transactions (Type, Time, "Sender Account", "Receiver Account", Status, Amount, Operator, Memo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                txn.type,
                txn.time.isoformat(),
                txn.sender_account,
                txn.receiver_account,
                txn.status,
                txn.amount,
                txn.operator,
                txn.memo,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def find_by_id(self, txn_id: int) -> Transaction | None:
        """
        Find a transaction by ID.

        Args:
            txn_id: The transaction ID to search for

        Returns:
            Transaction object if found, None otherwise
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT TransactionID, Type, Time, "Sender Account", "Receiver Account", Status, Amount, Operator, Memo
               FROM Transactions WHERE TransactionID = ?""",
            (txn_id,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return Transaction(
            id=row["TransactionID"],
            type=row["Type"],
            time=datetime.fromisoformat(row["Time"]),
            sender_account=row["Sender Account"],
            receiver_account=row["Receiver Account"],
            status=row["Status"],
            amount=row["Amount"],
            operator=row["Operator"],
            memo=row["Memo"],
        )

    def find_pending_transactions(self, limit: int) -> list[Transaction]:
        """
        Find pending transactions up to the specified limit.

        Args:
            limit: Maximum number of transactions to return

        Returns:
            List of pending transactions, ordered by TransactionID
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT TransactionID, Type, Time, "Sender Account", "Receiver Account", Status, Amount, Operator, Memo
               FROM Transactions WHERE Status = 'pending' LIMIT ?""",
            (limit,),
        )
        rows = cursor.fetchall()

        return [
            Transaction(
                id=row["TransactionID"],
                type=row["Type"],
                time=datetime.fromisoformat(row["Time"]),
                sender_account=row["Sender Account"],
                receiver_account=row["Receiver Account"],
                status=row["Status"],
                amount=row["Amount"],
                operator=row["Operator"],
                memo=row["Memo"],
            )
            for row in rows
        ]

    def find_by_account(self, account_no: str, limit: int) -> list[Transaction]:
        """
        Find transactions where the account is sender or receiver.

        Excludes transactions with status 'denied'.

        Args:
            account_no: The account number to search for
            limit: Maximum number of transactions to return

        Returns:
            List of transactions ordered by TransactionID DESC
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """SELECT TransactionID, Type, Time, "Sender Account", "Receiver Account", Status, Amount, Operator, Memo
               FROM Transactions
               WHERE ("Sender Account" = ? OR "Receiver Account" = ?) AND Status <> 'denied'
               ORDER BY TransactionID DESC LIMIT ?""",
            (account_no, account_no, limit),
        )
        rows = cursor.fetchall()

        return [
            Transaction(
                id=row["TransactionID"],
                type=row["Type"],
                time=datetime.fromisoformat(row["Time"]),
                sender_account=row["Sender Account"],
                receiver_account=row["Receiver Account"],
                status=row["Status"],
                amount=row["Amount"],
                operator=row["Operator"],
                memo=row["Memo"],
            )
            for row in rows
        ]

    def update_status(self, txn_id: int, status: str, operator: str) -> None:
        """
        Update the status and operator of a transaction.

        Args:
            txn_id: The transaction ID to update
            status: The new status value
            operator: The operator who performed the update
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE Transactions SET Status = ?, Operator = ? WHERE TransactionID = ?",
            (status, operator, txn_id),
        )
        self._conn.commit()
