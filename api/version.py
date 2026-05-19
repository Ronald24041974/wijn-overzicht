import sys, os, json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        results = {}
        # Test 1: sys.path
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, root)
        results["root"] = root
        results["lib_exists"] = os.path.isdir(os.path.join(root, "lib"))
        results["lib_files"] = os.listdir(os.path.join(root, "lib")) if results["lib_exists"] else []

        # Test 2: psycopg2
        try:
            import psycopg2
            results["psycopg2"] = "ok"
        except Exception as e:
            results["psycopg2"] = str(e)

        # Test 3: lib.db
        try:
            from lib.db import get_db
            results["lib_db"] = "ok"
        except Exception as e:
            results["lib_db"] = str(e)

        # Test 4: database connection
        try:
            from lib.db import load_wines
            wines = load_wines()
            results["db_connect"] = f"ok - {len(wines)} wijnen"
        except Exception as e:
            results["db_connect"] = str(e)

        body = json.dumps(results, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
