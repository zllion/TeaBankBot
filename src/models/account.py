"""Account data model."""

from dataclasses import dataclass


@dataclass
class Account:
    """Represents a bank account."""

    id: int
    account_no: str
    name: str
    amount: float
    pending: float
    share: float

    @property
    def total_balance(self) -> float:
        """Calculate total balance including pending amounts."""
        return self.amount + self.pending
