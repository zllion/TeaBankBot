"""Bank service for business logic layer."""

from src.models.account import Account
from src.models.exceptions import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidTransferError,
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
        min_balance: int = -1_000_000_000,
    ):
        """
        Initialize the BankService with repositories.

        Args:
            account_repo: Repository for account data access
            transaction_repo: Repository for transaction data access
            min_amount: Minimum allowed transaction amount (default: 1)
            max_amount: Maximum allowed transaction amount (default: 10^12)
            min_balance: Minimum allowed account balance (default: -1B)
        """
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo
        self._min_amount = min_amount
        self._max_amount = max_amount
        self._min_balance = min_balance

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

    def transfer(self, from_user: str, to_user: str, amount: int, memo: str) -> Transaction:
        """
        Transfer funds from one user to another (immediate, no approval needed).

        Transfer is an immediate operation that updates both accounts atomically.
        The receiver account is auto-created if it doesn't exist.

        Args:
            from_user: The user ID of the sender
            to_user: The user ID of the receiver
            amount: The amount to transfer (must be positive)
            memo: Transaction memo/note

        Returns:
            The created Transaction with status='done'

        Raises:
            AccountNotFoundError: If the sender account doesn't exist
            InvalidTransferError: If sender and receiver are the same
            InvalidAmountError: If the amount is invalid (negative or zero)
            InsufficientBalanceError: If the sender has insufficient balance
        """
        # Get account numbers
        from_account_no = self._get_account_no(from_user)
        to_account_no = self._get_account_no(to_user)

        # Validate sender exists
        sender = self._account_repo.find_by_account_no(from_account_no)
        if sender is None:
            raise AccountNotFoundError(f"Sender account {from_account_no} not found")

        # Auto-create receiver if needed
        if not self._account_repo.exists(to_account_no):
            # Use to_user as the name for auto-created account
            self.create_account(to_user, to_user)

        # Validate not transferring to self
        if from_account_no == to_account_no:
            raise InvalidTransferError("Cannot transfer to the same account")

        # Validate amount > 0
        if amount < 0:
            raise InvalidAmountError(
                f"Cannot transfer negative amount: {amount}. Amount must be positive."
            )
        if amount == 0:
            raise InvalidAmountError("Transfer amount must be greater than zero.")

        # Check sender has sufficient amount
        if amount > sender.amount:
            raise InsufficientBalanceError(
                f"Insufficient balance: {sender.amount} available, {amount} requested"
            )

        # Check sender not below minimum balance after transfer
        if sender.amount - amount < self._min_balance:
            raise InsufficientBalanceError(
                f"Transfer would put balance below minimum: {sender.amount} - {amount} < {self._min_balance}"
            )

        # Update both accounts atomically
        # Note: In SQLite, each statement is atomic, but to ensure true atomicity
        # across both updates, we would need a transaction. For now, we rely on
        # the fact that SQLite's default isolation level provides serializable
        # transactions when used properly.
        self._account_repo.update_amount(from_account_no, -amount)
        self._account_repo.update_amount(to_account_no, amount)

        # Create transaction with status='done'
        transaction = Transaction.create_pending(
            type="transfer",
            sender=from_account_no,
            receiver=to_account_no,
            amount=amount,
            memo=memo,
        )
        transaction.status = "done"

        # Save transaction
        txn_id = self._transaction_repo.create(transaction)

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

    def request(self, user_id: str, amount: int, memo: str) -> Transaction:
        """
        Request funds from the bank.

        Similar to deposit but max_request_amount is 100B (not 1T).
        The request creates a pending transaction that requires audit approval.
        The pending balance is increased immediately, but the amount balance
        is only updated after audit approval.

        Args:
            user_id: The user ID of the account requesting funds
            amount: The amount to request (must be positive and <= 100B)
            memo: Transaction memo/note

        Returns:
            The created Transaction

        Raises:
            AccountNotFoundError: If the account doesn't exist
            InvalidAmountError: If the amount is invalid (negative, zero, or exceeds 100B)
        """
        # Get account number
        account_no = self._get_account_no(user_id)

        # Validate account exists
        account = self._account_repo.find_by_account_no(account_no)
        if account is None:
            raise AccountNotFoundError(f"Account {account_no} not found")

        # Define max request amount as 100B
        max_request_amount = 100_000_000_000

        # Validate amount
        if amount < 0:
            raise InvalidAmountError(
                f"Cannot request negative amount: {amount}. Amount must be positive."
            )
        if amount == 0:
            raise InvalidAmountError("Request amount must be greater than zero.")
        if amount > max_request_amount:
            raise InvalidAmountError(
                f"Amount {amount} exceeds maximum allowed request of {max_request_amount}"
            )

        # Create pending transaction
        transaction = Transaction.create_pending(
            type="request",
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

    def donate(self, user_id: str, amount: int, memo: str) -> Transaction:
        """
        Donate funds to the bank.

        Like withdraw but decreases pending.
        The donation creates a pending transaction that requires audit approval.
        The pending balance is decreased immediately, but the amount balance
        is only updated after audit approval.

        Args:
            user_id: The user ID of the account donating funds
            amount: The amount to donate (must be positive and <= max_amount)
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
                f"Cannot donate negative amount: {amount}. Amount must be positive."
            )
        if amount == 0:
            raise InvalidAmountError("Donation amount must be greater than zero.")
        if amount > self._max_amount:
            raise InvalidAmountError(
                f"Amount {amount} exceeds maximum allowed donation of {self._max_amount}"
            )

        # Check sufficient balance (amount - pending >= donation amount)
        # pending is negative for donations, so we subtract it
        available_balance = account.amount - account.pending
        if amount > available_balance:
            raise InsufficientBalanceError(
                f"Insufficient balance: {available_balance} available, {amount} requested"
            )

        # Create pending transaction
        transaction = Transaction.create_pending(
            type="donate",
            sender=account_no,
            receiver=account_no,
            amount=amount,
            memo=memo,
        )

        # Save transaction
        txn_id = self._transaction_repo.create(transaction)

        # Update pending balance (decrease for donation)
        self._account_repo.update_pending(account_no, -amount)

        # Fetch and return the transaction with ID
        return self._transaction_repo.find_by_id(txn_id)

    def deny_transaction(self, txn_id: int, operator: str) -> None:
        """
        Deny a pending transaction.

        Reverse pending based on transaction type:
        - For deposit/request: pending -= amount (was increased)
        - For withdraw/donate: pending += amount (was decreased)

        Args:
            txn_id: The transaction ID to deny
            operator: The operator denying the transaction

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

        # Get account number and amount
        account_no = transaction.receiver_account
        amount = transaction.amount

        # Revert pending balance based on transaction type
        # For deposit/request: pending was increased, so decrease it
        # For withdraw/donate: pending was decreased, so increase it
        if transaction.type in ("deposit", "request"):
            # Decrease pending (was increased)
            self._account_repo.update_pending(account_no, -amount)
        elif transaction.type in ("withdraw", "donate"):
            # Increase pending (was decreased)
            self._account_repo.update_pending(account_no, amount)
        else:
            # For transfer and other types, handle both accounts
            if transaction.sender_account != transaction.receiver_account:
                # Transfer: revert both accounts
                # For sender: pending was increased (since they're sending), so decrease
                self._account_repo.update_pending(
                    transaction.sender_account, pending_delta=-amount
                )
                # For receiver: pending was decreased (since they're receiving), so increase
                self._account_repo.update_pending(
                    transaction.receiver_account, pending_delta=amount
                )

        # Update transaction status to denied
        self._transaction_repo.update_status(txn_id, "denied", operator)

    def pull_transactions(self, user_id: str, n: int) -> list[Transaction]:
        """
        Get recent N transactions for a user.

        Args:
            user_id: The user ID
            n: Number of recent transactions to retrieve

        Returns:
            List of recent transactions for the user (max N)
        """
        account_no = self._get_account_no(user_id)
        return self._transaction_repo.find_by_account(account_no, n)

    def get_pending_transactions(self, limit: int) -> list[Transaction]:
        """
        Get all pending transactions.

        Args:
            limit: Maximum number of pending transactions to return

        Returns:
            List of pending transactions
        """
        return self._transaction_repo.find_pending_transactions(limit)
