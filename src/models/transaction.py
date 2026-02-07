"""Transaction data model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Transaction:
    """Represents a banking transaction."""

    id: int | None
    type: str
    time: datetime
    sender_account: str
    receiver_account: str
    status: str
    amount: int
    operator: str | None
    memo: str

    @classmethod
    def create_pending(
        cls,
        type: str,
        sender: str,
        receiver: str,
        amount: int,
        memo: str,
    ) -> "Transaction":
        """
        Create a pending transaction with current timestamp.

        Args:
            type: The type of transaction (e.g., 'transfer', 'deposit')
            sender: The sender account number
            receiver: The receiver account number
            amount: The transaction amount
            memo: Transaction memo/note

        Returns:
            A new Transaction with id=None, status='pending', and current time
        """
        return cls(
            id=None,
            type=type,
            time=datetime.now(),
            sender_account=sender,
            receiver_account=receiver,
            status="pending",
            amount=amount,
            operator=None,
            memo=memo,
        )
