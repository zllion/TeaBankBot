
import random
import pygsheets
from datetime import datetime
import sqlite3
from sqlite3 import Error

class SQLBank():
    def __init__(self,sheet='TestBank',db='testbank.db'):
        self.gc = pygsheets.authorize(service_file='./teabank-9ce129712f0c.json')
        self.db = self.gc.open(sheet)
        self.transbook,self.accbook,self.pendbook=self.db.worksheets()
        self.conn = sqlite3.connect(db)
        self.cur = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        sql_create_accounts = '''CREATE TABLE IF NOT EXISTS "Accounts" (
        "id" INTEGER NOT NULL,
        "Account" TEXT NOT NULL UNIQUE,
        "Name" TEXT NOT NULL,
        "Amount" INTEGER,
        "Pending" INTEGER,
        "Share" INTEGER,
        PRIMARY KEY("id" AUTOINCREMENT)
        );'''
        sql_create_transactions = '''CREATE TABLE IF NOT EXISTS "Transactions" (
        "TransactionID" INTEGER NOT NULL UNIQUE,
        "Type" TEXT,
        "Time" TEXT,
        "Sender Account" TEXT,
        "Receiver Account" TEXT,
        "Status" TEXT,
        "Amount" INTEGER,
        "Operator" TEXT,
        "Memo" TEXT,
        PRIMARY KEY("TransactionID" AUTOINCREMENT)
        );'''
        self.cur.execute(sql_create_accounts)
        self.cur.execute(sql_create_transactions)

    # make a transaction record
    def _transaction(self,ty,n,sender,senderacc,receiver,receiveracc,status,memo=''):
        now = datetime.now()
        current_time = now.strftime("%D %H:%M:%S")
        self.cur.execute('''INSERT INTO Transactions ("Type","Time","Sender Account","Receiver Account","Status","Amount","Memo")
        VALUES (?,?,?,?,?,?,?)''',(ty,current_time,senderacc,receiveracc,status,n,memo))
        # update pending
        self.cur.execute("SELECT TransactionID FROM Transactions WHERE Time = ?",(current_time,))
        transid = self.cur.fetchone()[0]
        return


    # change balance
    def _balance_add(self,accNo,n):
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (accNo,))
        data=self.cur.fetchone()
        balance=data[3]
        self.cur.execute("UPDATE Accounts SET Amount = ? WHERE Account = ?",(balance+n,accNo))
        return


    # create account
    def CreateAccount(self,name: str,user_id: str):
        accNo = user_id[-9:]
        self.cur.execute("SELECT 1 FROM Accounts WHERE Account = ?", (accNo,))
        data=self.cur.fetchone()
        if data is None:
            sql = '''INSERT INTO Accounts ("Account", "Name", "Amount", "Pending", "Share")
            VALUES (?,?,0,0,0)'''
            self.cur.execute(sql,(accNo,name))
        else:
            raise ValueError('Account exits!')
        self.conn.commit()

    def Deposit(self,n,receiver,receiverid,memo=''):
        # prepare variable
        accNo = receiverid[-9:]
        # Account Check
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (accNo,))
        data=self.cur.fetchone()
        if data is None:
            raise ValueError('Account not found, please $register.')

        #eligibility check
        if n < 0:
            self._transaction('deposit',n,'','',receiver,accNo,'denied',memo=memo+'/Err: Cannot Deposit negative isk')
            raise ValueError("Cannot Deposit negative isk")
        if n > 1000000000000:
            raise ValueError("That's too large!")
        pending = data[4]
        self.cur.execute("UPDATE Accounts SET Pending = ? WHERE Account = ?",(pending+n,accNo))
        # write record
        self._transaction('deposit',n,'','',receiver,accNo,'pending',memo)
        self.conn.commit()
        return

    def Withdraw(self,n,receiver,receiverid,memo=''):
        # prepare variable
        accNo = receiverid[-9:]
        # Account Check
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (accNo,))
        data=self.cur.fetchone()
        if data is None:
            raise ValueError('Account not found, please $register.')

        #eligibility check
        if n < 0:
            self._transaction('withdraw',n,'','',receiver,accNo,'denied',memo=memo + '/Err: Cannot Withdraw isk from vacuum')
            raise ValueError("Cannot Withdraw isk from vacuum")
        if n > 1000000000000:
            raise ValueError("That's too large!")
        balance, pending = data[3],data[4]
        if n > balance+pending:
            self._transaction('withdraw',n,'','',receiver,accNo,'denied',memo=memo + "/Err: Balance is not enough")
            raise ValueError("Balance is not enough")
        self.cur.execute("UPDATE Accounts SET Pending = ? WHERE Account = ?",(pending-n,accNo))
        # write record
        self._transaction('withdraw',n,'','',receiver,accNo,'pending',memo)
        self.conn.commit()
        return

    def Transfer(self,n,sender,senderid,receiver,receiverid,memo=''):
        senderacc = str(senderid)[-9:]
        receiveracc = str(receiverid)[-9:]
        if senderacc == receiveracc:
            raise ValueError('Error: Transfer between same account.')
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (senderacc,))
        data=self.cur.fetchone()
        if data is None:
            raise ValueError('Account not found, please $register.')
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (receiveracc,))
        data2=self.cur.fetchone()
        if data2 is None:
            self.CreateAccount(receiver,receiverid)

        # eligibility check
        if n < 0:
            self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'denied',memo=memo + "/Err: negative money")
            raise ValueError("Please don't send negative isk, you cannot get money from other's account.")
        balance, pending = data[3],data[4]
        # check validity
        if n > balance+pending:
            self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'denied',memo=memo + "/Err: Balance is not enough")
            raise ValueError("Balance is not enough")
        if balance < -1000000000:
            self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'denied',memo=memo+"/Err: Isk pending please request for auditing")
            raise ValueError("Isk pending please request for auditing")
        # update balance
        self._balance_add(senderacc,-n)
        self._balance_add(receiveracc,n)
        # write record
        self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'done',memo)
        self.conn.commit()
        return

    def Check(self,user,userid):
        accNo = str(userid)[-9:]
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (accNo,))
        data=self.cur.fetchone()
        if data is None:
            raise ValueError('Account not found, please $register.')
        balance, pending = data[3],data[4]
        return balance, pending

    def PullTransactions(self,userid,n):
        #pull recent n transactions
        accNo = str(userid)[-9:]
        self.cur.execute('''
        SELECT Transactions.TransactionID,Transactions.Time,Transactions.Amount,Transactions.Type,Accounts.Name,Transactions.Status
        FROM Transactions JOIN Accounts
        ON Transactions."Receiver Account"=Accounts.Account
        WHERE Transactions."Receiver Account"=? OR Transactions."Sender Account"=?
        ''',(accNo,accNo))
        data = self.cur.fetchall()[-n:]
        if data is None:
            raise ValueError('No recent transactions for this account, or no account.')
        return data


    def GetPendings(self):
        self.cur.execute(
            '''
            SELECT Transactions.TransactionID,Transactions.Time,Transactions.Amount,Transactions.Type,Accounts.Name
            FROM Transactions JOIN Accounts
            ON Transactions."Receiver Account"=Accounts.Account
            WHERE Transactions.Status = ?
            ''',
            ('pending',))
        data = self.cur.fetchall()
        return data

    def _update_gs(self,sheet,data):
        sheet.update_values('A3',data)


    def BackUpGS(self):
        self.cur.execute(
            '''
            SELECT Transactions.TransactionID,Transactions.Type,Transactions.Time,temp1.Name,
            Transactions."Sender Account", temp2.Name,Transactions."Receiver Account",Transactions.Amount,
            Transactions.Status,Transactions.Memo
            FROM Transactions
            LEFT JOIN Accounts AS temp1 ON Transactions."Sender Account"=temp1.Account
            LEFT JOIN Accounts AS temp2 ON Transactions."Receiver Account"=temp2.Account
            ;''')
        data = [list(line) for line in self.cur.fetchall()]
        self._update_gs(self.transbook,data)
        self.cur.execute('''SELECT Account, Name, Amount, Pending, Share From Accounts''')
        data = [list(line) for line in self.cur.fetchall()]
        self._update_gs(self.accbook,data)
        self.cur.execute('''
        SELECT Transactions.TransactionID, Transactions.Time, Transactions.Operator, Transactions.Type,
        Accounts.Name, Transactions.Amount
        FROM Transactions
        JOIN Accounts ON Transactions."Receiver Account"=Accounts.Account
        WHERE Transactions.Operator IS NOT NULL
        ''')
        data = [list(line) for line in self.cur.fetchall()]
        self._update_gs(self.pendbook,data)
        self.conn.commit()
        return data

    def Approve(self,transid,operator):
        self.cur.execute("SELECT * FROM Transactions WHERE TransactionID = ?", (transid,))
        data1=self.cur.fetchone()
        #print(data1)
        if data1 is None:
            raise ValueError('Target Transaction Not Found')
        # get transaction data
        amount, accNo = data1[6], data1[4]
        # Account Check
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (accNo,))
        data2=self.cur.fetchone()
        if data2 is None:
            raise ValueError('Account not found')
        balance, pending = data2[3],data2[4]
        # update
        if data1[1] == 'deposit':
            amount = amount
        elif data1[1] == 'withdraw':
            amount = -amount
        else:
            raise ValueError('Wrong status.')

        self.cur.execute("UPDATE Accounts SET Pending = ?, Amount = ? WHERE Account = ?",(pending-amount,balance+amount,accNo))
        # self.cur.execute("UPDATE Accounts SET Amount = ? WHERE Account = ?",(balance+n,accNo))
        self.cur.execute("UPDATE Transactions SET Status = ?, Operator = ? WHERE TransactionID = ?",('done',operator,transid))
        self.conn.commit()


    def Deny(self,transid,operator):
        self.cur.execute("SELECT * FROM Transactions WHERE TransactionID = ?", (transid,))
        data1=self.cur.fetchone()
        if data1 is None:
            raise ValueError('Target Transaction Not Found')
        # get transaction data
        amount, accNo = data1[6], data1[4]
        # Account Check
        self.cur.execute("SELECT * FROM Accounts WHERE Account = ?", (accNo,))
        data2=self.cur.fetchone()
        if data2 is None:
            raise ValueError('Account not found')
        balance, pending = data2[3],data2[4]
        # update
        if data1[1] == 'deposit':
            amount = amount
        elif data1[1] == 'withdraw':
            amount = -amount
        else:
            raise ValueError('Wrong status.')
        self.cur.execute("UPDATE Accounts SET Pending = ? WHERE Account = ?",(pending-amount,accNo))
        self.cur.execute("UPDATE Transactions SET Status = ?, Operator = ? WHERE TransactionID = ?",('denied',operator,transid))
        self.conn.commit()
