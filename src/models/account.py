"""Account data model."""

from dataclasses import dataclass


@dataclass
class Account:
    """Represents a bank account."""

    id: int
    account_no: str
    name: str
    amount: int
    pending: int
    share: int

    @property
    def total_balance(self) -> int:
        """Calculate total balance including pending amounts."""
        return self.amount + self.pending
