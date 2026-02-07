# TeaBankBot 重构设计文档

**日期**: 2026-02-07
**类型**: 渐进式重构
**目标**: 代码结构分层 + 代码质量提升

---

## 1. 概述

TeaBankBot 是一个为游戏公会（EVE Echoes）设计的 Discord 银行管理机器人。本次重构旨在：

1. **代码结构** - 引入分层架构，分离关注点
2. **代码质量** - 添加类型注解、完善测试、改进基础设施

重构采用**渐进式**策略，保持最小改动，逐步改善代码结构。

---

## 2. 架构设计

### 2.1 分层架构

```
teabot.py (Bot 入口)
    ↓
cogs/ (命令层 - 只处理 Discord 交互)
    ↓
services/ (服务层 - 业务逻辑编排)
    ↓
repositories/ (数据访问层 - 数据库操作)
    ↓
SQLite Database
```

### 2.2 各层职责

| 层 | 职责 |
|---|---|
| **Cogs** | Discord 消息解析、响应格式化、emoji 交互 |
| **Services** | 业务规则：账户验证、余额检查、交易状态流转 |
| **Repositories** | SQLite 操作封装，提供 CRUD 接口 |
| **Models** | 数据结构定义、类型注解、自定义异常 |

---

## 3. 目录结构

```
teabankbot/
├── src/
│   ├── __init__.py
│   ├── models/              # 数据模型
│   │   ├── __init__.py
│   │   ├── account.py       # Account 数据类
│   │   ├── transaction.py   # Transaction 数据类
│   │   └── exceptions.py    # 自定义异常
│   │
│   ├── repositories/        # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py          # 基础 Repository 接口
│   │   ├── account_repo.py  # 账户表操作
│   │   └── transaction_repo.py  # 交易表操作
│   │
│   ├── services/            # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── bank_service.py  # 银行业务逻辑
│   │   └── audit_service.py # 审计业务逻辑
│   │
│   └── bot.py               # Bot 初始化
│
├── cogs/                    # Discord 命令
│   ├── __init__.py
│   ├── bankcmd.py           # 只处理 Discord 交互
│   └── test.py
│
├── tests/                   # 测试目录
│   ├── __init__.py
│   ├── test_repositories.py
│   ├── test_services.py
│   └── fixtures/
│       └── test_db.py
│
├── config/                  # 配置文件
│   ├── __init__.py
│   └── settings.py          # 环境变量管理
│
├── teabot.py                # 入口点（简化）
├── testbot.py               # 测试入口点
├── backup.py                # 保留
├── requirements.txt         # 依赖列表
└── CLAUDE.md                # 已存在
```

---

## 4. 数据模型 (models/)

### 4.1 Account

```python
from dataclasses import dataclass

@dataclass
class Account:
    id: int
    account_no: str    # 账号（user_id 后9位）
    name: str
    amount: int        # 已确认余额
    pending: int       # 待审核余额
    share: int
```

### 4.2 Transaction

```python
@dataclass
class Transaction:
    id: int
    type: str          # deposit/withdraw/transfer/request/donate/admin-send
    time: str
    sender_account: str
    receiver_account: str
    status: str        # pending/done/denied
    amount: int
    operator: str | None
    memo: str
```

### 4.3 自定义异常

```python
class BankError(Exception): pass

class AccountNotFoundError(BankError): pass
class AccountAlreadyExistsError(BankError): pass
class InsufficientBalanceError(BankError): pass
class InvalidAmountError(BankError): pass
class TransactionNotFoundError(BankError): pass
class InvalidTransactionStatusError(BankError): pass
class InvalidTransferError(BankError): pass
class UnauthorizedError(BankError): pass
```

---

## 5. 数据访问层 (repositories/)

### 5.1 AccountRepository

```python
class AccountRepository:
    def find_by_account_no(self, account_no: str) -> Account | None
    def create(self, account: Account) -> None
    def update_pending(self, account_no: str, delta: int) -> None
    def update_amount(self, account_no: str, delta: int) -> None
    def exists(self, account_no: str) -> bool
    def create_table(self) -> None
```

### 5.2 TransactionRepository

```python
class TransactionRepository:
    def create(self, txn: Transaction) -> int
    def find_pending_transactions(self, limit: int) -> list[Transaction]
    def find_by_account(self, account_no: str, limit: int) -> list[Transaction]
    def find_by_id(self, txn_id: int) -> Transaction | None
    def update_status(self, txn_id: int, status: str, operator: str) -> None
    def create_table(self) -> None
```

---

## 6. 业务逻辑层 (services/)

### 6.1 BankService 接口

```python
class BankService:
    def __init__(self, account_repo: AccountRepository,
                 transaction_repo: TransactionRepository):
        ...

    # 账户相关
    def create_account(self, user_id: str, name: str) -> Account
    def get_balance(self, user_id: str) -> tuple[int, int]

    # 交易相关（创建 pending 记录）
    def deposit(self, user_id: str, amount: int, memo: str) -> Transaction
    def withdraw(self, user_id: str, amount: int, memo: str) -> Transaction
    def transfer(self, from_user: str, to_user: str, amount: int, memo: str) -> Transaction
    def request(self, user_id: str, amount: int, memo: str) -> Transaction
    def donate(self, user_id: str, amount: int, memo: str) -> Transaction

    # 审计相关
    def approve_transaction(self, txn_id: int, operator: str) -> None
    def deny_transaction(self, txn_id: int, operator: str) -> None

    # 查询相关
    def pull_transactions(self, user_id: str, n: int) -> list[Transaction]
    def get_pending_transactions(self, limit: int) -> list[Transaction]
```

### 6.2 业务规则

| 操作 | 规则 |
|---|---|
| `deposit` | 金额 > 0，≤ 1T |
| `withdraw` | 金额 > 0，≤ 1T，余额 + pending ≥ 金额 |
| `request` | 金额 > 0，≤ 100M |
| `donate` | 金额 > 0，≤ 1T，余额 + pending ≥ 金额 |
| `transfer` | 金额 > 0，余额 ≥ 金额，不能转给自己，余额 ≥ -1B |

---

## 7. 配置管理 (config/settings.py)

```python
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
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
    blocked_channel_ids: list[int] = None

    # Owner
    owner_id: int = 356096513828454411
    admin_role_name: str = '管理员'

    @classmethod
    def load(cls) -> 'Settings':
        return cls(
            discord_token=os.getenv('DISCORD_TOKEN', ''),
            discord_test_token=os.getenv('DISCORD_TOKEN_TEST', ''),
        )
```

---

## 8. 依赖注入

```python
# src/bot.py
class BankBot(commands.Bot):
    def __init__(self, settings: Settings, is_test: bool = False):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(
            command_prefix='¥' if is_test else '$',
            owner_id=settings.owner_id,
            intents=intents
        )

        # 初始化依赖
        db_path = settings.test_db_path if is_test else settings.prod_db_path
        conn = sqlite3.connect(db_path)

        self.account_repo = AccountRepository(conn)
        self.transaction_repo = TransactionRepository(conn)
        self.bank_service = BankService(self.account_repo, self.transaction_repo)

        # 加载 cogs
        self.load_extension('cogs.bankcmd')
```

---

## 9. 测试策略

### 9.1 Service 层测试覆盖

| 测试类 | 覆盖场景 |
|---|---|
| `TestCreateAccount` | 正常创建、重复账户、账号截取 |
| `TestDeposit` | 正常存款、账户不存在、负数、零、超限、边界值、empty memo |
| `TestWithdraw` | 余额充足、账户不存在、负数、超限、余额不足、恰好相等、pending计算 |
| `TestTransfer` | 正常转账、自动创建接收方、发送方不存在、自己转自己、负数、余额不足、深度负余额、双方余额更新 |
| `TestRequestAndDonate` | 正常请求、请求超限、正常捐赠、捐赠超限 |
| `TestAudit` | 批准存款/取款/请求、拒绝交易、不存在交易、重复操作 |
| `TestGetBalance` | 正常查询、账户不存在 |
| `TestPullTransactions` | 查询最近N笔、排除已拒绝 |

### 9.2 测试结构

```
tests/
├── fixtures/
│   └── test_db.py      # 内存数据库 fixture
├── test_repositories.py # Repository 层测试
└── test_services.py     # Service 层测试
```

---

## 10. 依赖文件 (requirements.txt)

```
discord.py>=2.3.0
python-dotenv>=1.0.0
pygsheets>=2.0.0
tabulate>=0.9.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

## 11. 实施步骤

1. 创建目录结构
2. 实现 Models（数据类和异常）
3. 实现 Repositories（数据访问层）
4. 实现 Services（业务逻辑层）
5. 重构 Cogs（简化为只处理 Discord 交互）
6. 更新配置管理
7. 编写测试
8. 更新入口文件
