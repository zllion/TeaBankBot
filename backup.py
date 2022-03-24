import shutil
from datetime import date
import os
from distutils.dir_util import copy_tree

today = date.today()
date_format = today.strftime("_%m_%d_%Y")
src_file = './teabank.db'
dest_file = f'../backup/teabank{date_format}.db'
try:
   shutil.copy2(src_file, dest_file)

except FileNotFoundError:
    print("File does not exists!,\
    please give the complete path")
