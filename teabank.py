
import random
import gspread
from gspread.exceptions import CellNotFound
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

def next_available_row(worksheet):
    str_list = worksheet.col_values(1)
    return len(str_list)+1

# Bank Class
class Bank():
    def __init__(self,sheet):
        self.gc = gspread.service_account(filename='./teabank-9ce129712f0c.json')
        self.db = self.gc.open(sheet)
        self.transbook,self.accbook,self.pendbook=self.db.worksheets()
        #self.transbook = self.db.sheet1
        #self.accbook = self.db.sheet2
        #self.pendbook = self.db.sheet3
        self.transindex = next_available_row(self.transbook)
        self.accindex = next_available_row(self.accbook)
        self.pendindex = next_available_row(self.pendbook)
        self.pendstart = 0

    # make a transaction record to google sheet
    def _transaction(self,ty,n,sender,senderacc,receiver,receiveracc,status,memo=''):
        now = datetime.now()
        current_time = now.strftime("%D %H:%M:%S")
        transNo = "{:07d}".format(self.transindex-4)
        self.transbook.update('A'+str(self.transindex)+':'+'J'+str(self.transindex),\
                              [[transNo,ty,current_time,sender,senderacc,receiver,receiveracc,n,status,memo]])
        # update pending
        if (ty == 'deposit' or ty == 'withdraw') and status!='denied':
            self._pending(transNo,current_time,'',ty,receiver,n,status)
        self.transindex += 1
        return


    # change balance
    def _balance_add(self,row,n):
        balance=int(self.accbook.cell(row,3).value)
        self.accbook.update_cell(row,3,balance+n)
        pass


    # make pending record
    def _pending(self,transNo,ctime,rtime,ty,name,n,status='pending'):
        self.pendbook.update('A'+str(self.pendindex)+':'+'G'+str(self.pendindex),\
                             [[transNo,ctime,rtime,ty,name,n,status]])
        self.pendindex += 1
        return

    # create account
    def CreateAccount(self,name: str,user_id: str):
        accNo = user_id[-6:]
        try:
            _ = self.accbook.find(accNo)
        except CellNotFound:
            pass
        else:
            raise ValueError('Account exist with account number: ' + accNo)
        self.accbook.update('A'+str(self.accindex)+':'+'E'+str(self.accindex),\
                            [[accNo,name,0,0]])
        self.accindex += 1
        pass

    def Deposit(self,n,receiver,receiverid):
        # prepare variable
        accno = receiverid[-6:]
        i = self.accbook.find(accno).row
        # eligibility check
        if n < 0:
            self._transaction('deposit',n,'','',receiver,accno,'denied',memo='Err: Cannot Deposit negative isk')
            raise ValueError("Cannot Deposit negative isk")
        pending = int(self.accbook.cell(i,4).value)
        self.accbook.update_cell(i,4,pending+n)
        # write record
        self._transaction('deposit',n,'','',receiver,accno,'pending')

        return

    def Withdraw(self,n,receiver,receiverid):
        accno = receiverid[-6:]
        i = self.accbook.find(accno).row
        if n < 0:
            self._transaction('withdraw',n,'','',receiver,accno,'denied',memo="Err: Cannot Withdraw isk from vacuum")
            raise ValueError("Cannot Withdraw isk from vacuum")
        balance = int(self.accbook.cell(i,3).value)
        pending = int(self.accbook.cell(i,4).value)
        if n > balance+pending:
            self._transaction('withdraw',n,'','',receiver,accno,'denied',memo="Err: Balance is not enough")
            raise ValueError("Balance is not enough")
        self.accbook.update_cell(i,4,pending-n)
        # write record
        self._transaction('withdraw',n,'','',receiver,accno,'pending')

        return

    def Transfer(self,n,sender,senderid,receiver,receiverid,memo=None):
        senderacc = str(senderid)[-6:]
        receiveracc = str(receiverid)[-6:]
        i = self.accbook.find(senderacc).row
        try:
            j = self.accbook.find(receiveracc).row
        except CellNotFound:
            self.CreateAccount(receiver,receiverid)
            j = self.accindex - 1
        # eligibility check
        if n < 0:
            self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'denied',memo="Err: Please don't, use $request")
            raise ValueError("Please don't send negative isk, you cannot get money from other's account.")
        balance = int(self.accbook.cell(i,3).value)
        pending = int(self.accbook.cell(i,4).value)
        # check validity
        if n > balance+pending:
            self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'denied',memo="Err: Balance is not enough")
            raise ValueError("Balance is not enough")
        if balance < -1000000000:
            self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'denied',memo="Err: Isk pending please request for auditing")
            raise ValueError("Isk pending please request for auditing")
        # update balance
        self._balance_add(i,-n)
        self._balance_add(j,n)
        # write record
        self._transaction('transfer',n,sender,senderacc,receiver,receiveracc,'done',memo)
        return

    def Check(self,user,userid):
        accNo = str(userid)[-6:]
        i = self.accbook.find(accNo).row
        balance = int(self.accbook.cell(i,3).value)
        pending = int(self.accbook.cell(i,4).value)
        return balance, pending

    def _find_pend_start(self):
        if self.pendstart == 0:
            lst = self.pendbook.col_values(7)
            i = 3
            while i < self.pendindex:
                if lst[i-1] == 'pending':
                    break
                i += 1
            self.pendstart = i
        return

    def GetPendings(self):
        self._find_pend_start()
        i = self.pendstart
        pend = self.pendbook.get_all_values()[i-1:self.pendindex-1]
        #pend = []
        #while i < self.pendindex:
        #    print(i)
        #    pend.append(self.pendbook.row_values(i))
        return pend


    def Approve(self,transid):
        try:
            i = self.pendbook.find(transid).row
            j = self.transbook.find(transid).row
        except CellNotFound:
            raise ValueError('Wrong transaction id: '+transid)
        if i != self.pendstart:
            raise ValueError('You might skipped some pending transactions.')
        # get number and rows
        amount = int(self.pendbook.cell(i,6).value)
        accNo = self.transbook.cell(j,7).value
        k = self.accbook.find(accNo).row
        balance = int(self.accbook.cell(k,3).value)
        pending = int(self.accbook.cell(k,4).value)
        # update
        if self.pendbook.cell(i,4).value == 'deposit':
            amount = amount
        elif self.pendbook.cell(i,4).value == 'withdraw':
            amount = -amount
        else:
            raise ValueError('Wrong status.')
        self.accbook.update_cell(k,3,balance+amount)
        self.accbook.update_cell(k,4,pending-amount)
        self.pendbook.update_cell(i,7,'done')
        self.transbook.update_cell(j,9,'done')
        self.pendstart = i+1


    def Deny(self,transid):
        try:
            i = self.pendbook.find(transid).row
            j = self.transbook.find(transid).row
        except CellNotFound:
            raise ValueError('Wrong transaction id.')
        if i != self.pendstart:
            raise ValueError('You might skipped some pending transactions.')
        # get number and rows
        amount = int(self.pendbook.cell(i,6).value)
        accNo = self.transbook.cell(j,7).value
        k = self.accbook.find(accNo).row
        pending = int(self.accbook.cell(k,4).value)
        # update
        if self.pendbook.cell(i,4).value == 'deposit':
            amount = amount
        elif self.pendbook.cell(i,4).value == 'withdraw':
            amount = -amount
        else:
            raise ValueError('Wrong status.')
        self.accbook.update_cell(k,4,pending-amount)
        self.pendbook.update_cell(i,7,'denied')
        self.transbook.update_cell(j,9,'denied')
        self.pendstart = i+1
