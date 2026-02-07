"""Bank service for business logic layer."""

from src.models.account import Account
from src.models.exceptions import AccountAlreadyExistsError, AccountNotFoundError
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
