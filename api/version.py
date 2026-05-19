import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.helpers import BaseHandler

_START = str(int(time.time()))

class handler(BaseHandler):
    def do_GET(self):
        self.json_response(200, {"version": _START})
