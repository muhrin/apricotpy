import logging
import tempfile
import os
import sys

path = os.path.abspath(os.path.dirname(__file__))
if path not in sys.path:
    sys.path.append(path)

testfile = os.path.join(tempfile.gettempdir(), 'apricotpy_unittest.log')
try:
    os.remove(testfile)
except OSError:
    pass
print("Logging test to '{}'".format(testfile))
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)s()] %(message)s"
logging.basicConfig(filename=testfile, level=logging.DEBUG, format=FORMAT)
