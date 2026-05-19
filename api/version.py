import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from _helpers import BaseHandler
import time

_START = str(int(time.time()))

class handler(BaseHandler):
    def do_GET(self):
        self.json_response(200, {"version": _START})
