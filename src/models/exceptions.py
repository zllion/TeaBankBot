"""Custom exceptions for the banking system."""


class BankError(Exception):
    """Base exception for all banking-related errors."""
    pass


class AccountNotFoundError(BankError):
    """Raised when an account cannot be found."""
    pass


class AccountAlreadyExistsError(BankError):
    """Raised when attempting to create an account that already exists."""
    pass


class InsufficientBalanceError(BankError):
    """Raised when an account has insufficient balance for a transaction."""
    pass


class InvalidAmountError(BankError):
    """Raised when an invalid amount is provided (e.g., negative amount)."""
    pass


class TransactionNotFoundError(BankError):
    """Raised when a transaction cannot be found."""
    pass


class InvalidTransactionStatusError(BankError):
    """Raised when an invalid transaction status is provided."""
    pass


class InvalidTransferError(BankError):
    """Raised when a transfer operation is invalid (e.g., sender == receiver)."""
    pass


class UnauthorizedError(BankError):
    """Raised when a user is not authorized to perform an action."""
    pass
