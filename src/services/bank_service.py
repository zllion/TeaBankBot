"""Bank service for business logic layer."""

from src.models.account import Account
from src.models.exceptions import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidTransactionStatusError,
    TransactionNotFoundError,
)
from src.models.transaction import Transaction
from src.repositories.account_repo import AccountRepository
from src.repositories.transaction_repo import TransactionRepository


class BankService:
    """Service layer for banking operations."""

    def __init__(
        self,
        account_repo: AccountRepository,
        transaction_repo: TransactionRepository,
        min_amount: int = 1,
        max_amount: int = 1000000000000,
    ):
        """
        Initialize the BankService with repositories.

        Args:
            account_repo: Repository for account data access
            transaction_repo: Repository for transaction data access
            min_amount: Minimum allowed transaction amount (default: 1)
            max_amount: Maximum allowed transaction amount (default: 10^12)
        """
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo
        self._min_amount = min_amount
        self._max_amount = max_amount

    def _get_account_no(self, user_id: str) -> str:
        """
        Extract the last 9 digits from user_id to form account number.

        Args:
            user_id: The user ID string

        Returns:
            The last 9 digits (or fewer if user_id is shorter)
        """
        return user_id[-9:]

    def _get_or_create_account(self, account_no: str, name: str) -> Account:
        """
        Get existing account or create a new one.

        This is a helper method for operations that need to ensure
        an account exists (like transfers where receiver might not exist).

        Args:
            account_no: The account number
            name: The account name (used only if creating new account)

        Returns:
            The existing or newly created Account
        """
        account = self._account_repo.find_by_account_no(account_no)
        if account is None:
            # Create new account with zero balances
            new_account = Account(
                id=0,  # ID will be set by database
                account_no=account_no,
                name=name,
                amount=0,
                pending=0,
                share=0,
            )
            self._account_repo.create(new_account)
            # Fetch the created account to get the assigned ID
            account = self._account_repo.find_by_account_no(account_no)
        return account

    def create_account(self, user_id: str, name: str) -> Account:
        """
        Create a new account.

        Args:
            user_id: The user ID (Discord ID or similar)
            name: The account holder's name

        Returns:
            The created Account

        Raises:
            AccountAlreadyExistsError: If an account with this user_id already exists
        """
        account_no = self._get_account_no(user_id)

        # Check if account already exists
        if self._account_repo.exists(account_no):
            raise AccountAlreadyExistsError(f"Account {account_no} already exists")

        # Create new account with zero balances
        new_account = Account(
            id=0,  # ID will be set by database
            account_no=account_no,
            name=name,
            amount=0,
            pending=0,
            share=0,
        )

        self._account_repo.create(new_account)

        # Fetch and return the created account
        return self._account_repo.find_by_account_no(account_no)

    def get_balance(self, user_id: str) -> tuple[int, int]:
        """
        Get the balance for an account.

        Args:
            user_id: The user ID

        Returns:
            A tuple of (amount, pending) balances

        Raises:
            AccountNotFoundError: If the account doesn't exist
        """
        account_no = self._get_account_no(user_id)
        account = self._account_repo.find_by_account_no(account_no)

        if account is None:
            raise AccountNotFoundError(f"Account {account_no} not found")

        return account.amount, account.pending

    def deposit(self, user_id: str, amount: int, memo: str) -> Transaction:
        """
        Deposit funds into an account.

        The deposit creates a pending transaction that requires audit approval.
        The pending balance is increased immediately, but the amount balance
        is only updated after audit approval.

        Args:
            user_id: The user ID of the account to deposit to
            amount: The amount to deposit (must be positive and <= max_amount)
            memo: Transaction memo/note

        Returns:
            The created Transaction

        Raises:
            AccountNotFoundError: If the account doesn't exist
            InvalidAmountError: If the amount is invalid (negative, zero, or exceeds max)
        """
        # Get account number
        account_no = self._get_account_no(user_id)

        # Validate account exists
        account = self._account_repo.find_by_account_no(account_no)
        if account is None:
            raise AccountNotFoundError(f"Account {account_no} not found")

        # Validate amount
        if amount < 0:
            raise InvalidAmountError(
                f"Cannot deposit negative amount: {amount}. Amount must be positive."
            )
        if amount == 0:
            raise InvalidAmountError("Deposit amount must be greater than zero.")
        if amount > self._max_amount:
            raise InvalidAmountError(
                f"Amount {amount} exceeds maximum allowed deposit of {self._max_amount}"
            )

        # Create pending transaction
        transaction = Transaction.create_pending(
            type="deposit",
            sender=account_no,
            receiver=account_no,
            amount=amount,
            memo=memo,
        )

        # Save transaction
        txn_id = self._transaction_repo.create(transaction)

        # Update pending balance
        self._account_repo.update_pending(account_no, amount)

        # Fetch and return the transaction with ID
        return self._transaction_repo.find_by_id(txn_id)

    def withdraw(self, user_id: str, amount: int, memo: str) -> Transaction:
        """
        Withdraw funds from an account.

        The withdrawal creates a pending transaction that requires audit approval.
        The pending balance is decreased immediately, but the amount balance
        is only updated after audit approval.

        Args:
            user_id: The user ID of the account to withdraw from
            amount: The amount to withdraw (must be positive and <= max_amount)
            memo: Transaction memo/note

        Returns:
            The created Transaction

        Raises:
            AccountNotFoundError: If the account doesn't exist
            InvalidAmountError: If the amount is invalid (negative, zero, or exceeds max)
            InsufficientBalanceError: If the account has insufficient balance
        """
        # Get account number
        account_no = self._get_account_no(user_id)

        # Validate account exists
        account = self._account_repo.find_by_account_no(account_no)
        if account is None:
            raise AccountNotFoundError(f"Account {account_no} not found")

        # Validate amount
        if amount < 0:
            raise InvalidAmountError(
                f"Cannot withdraw negative amount: {amount}. Amount must be positive."
            )
        if amount == 0:
            raise InvalidAmountError("Withdrawal amount must be greater than zero.")
        if amount > self._max_amount:
            raise InvalidAmountError(
                f"Amount {amount} exceeds maximum allowed withdrawal of {self._max_amount}"
            )

        # Check sufficient balance (amount - pending >= withdrawal amount)
        # pending is negative for withdrawals, so we subtract it
        available_balance = account.amount - account.pending
        if amount > available_balance:
            raise InsufficientBalanceError(
                f"Insufficient balance: {available_balance} available, {amount} requested"
            )

        # Create pending transaction
        transaction = Transaction.create_pending(
            type="withdraw",
            sender=account_no,
            receiver=account_no,
            amount=amount,
            memo=memo,
        )

        # Save transaction
        txn_id = self._transaction_repo.create(transaction)

        # Update pending balance (decrease for withdrawal)
        self._account_repo.update_pending(account_no, -amount)

        # Fetch and return the transaction with ID
        return self._transaction_repo.find_by_id(txn_id)

    def approve_transaction(self, txn_id: int, operator: str) -> None:
        """
        Approve a pending transaction.

        For deposit/request transactions: pending -= amount, amount += amount
        For withdraw/donate transactions: pending += amount, amount -= amount

        Args:
            txn_id: The transaction ID to approve
            operator: The operator approving the transaction

        Raises:
            TransactionNotFoundError: If the transaction doesn't exist
            InvalidTransactionStatusError: If the transaction is not in 'pending' status
        """
        # Find transaction
        transaction = self._transaction_repo.find_by_id(txn_id)
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {txn_id} not found")

        # Check status is pending
        if transaction.status != "pending":
            raise InvalidTransactionStatusError(
                f"Transaction {txn_id} is not in pending status"
            )

        # Get account number
        account_no = transaction.receiver_account
        amount = transaction.amount

        # Update balances based on transaction type
        # For deposit/request: pending -= amount, amount += amount
        # For withdraw/donate: pending += amount, amount -= amount
        if transaction.type in ("deposit", "request"):
            # Decrease pending (was increased), increase amount
            self._account_repo.update_pending_and_amount(
                account_no, pending_delta=-amount, amount_delta=amount
            )
        elif transaction.type in ("withdraw", "donate"):
            # Increase pending (was decreased), decrease amount
            self._account_repo.update_pending_and_amount(
                account_no, pending_delta=amount, amount_delta=-amount
            )
        else:
            # For transfer and other types, we might need different logic
            # For now, assume sender/receiver both need updates
            if transaction.sender_account != transaction.receiver_account:
                # Transfer: update both accounts
                # For sender: pending += amount, amount -= amount
                self._account_repo.update_pending_and_amount(
                    transaction.sender_account,
                    pending_delta=amount,
                    amount_delta=-amount,
                )
                # For receiver: pending -= amount, amount += amount
                self._account_repo.update_pending_and_amount(
                    transaction.receiver_account,
                    pending_delta=-amount,
                    amount_delta=amount,
                )

        # Update transaction status to done
        self._transaction_repo.update_status(txn_id, "done", operator)
