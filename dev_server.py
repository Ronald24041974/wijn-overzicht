"""
Lokale dev-server voor Wijnoverzicht.
Gebruik: python3 dev_server.py [port]  (standaard 3000)
"""
import sys, os, re, importlib
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Laad .env bestand
def _load_env():
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()
os.environ['DEV_MODE'] = '1'

REWRITES = [
    (r'^/api/wine-thumb$',       '/api/wine_thumb'),
    (r'^/api/wine-image$',       '/api/wine_image'),
    (r'^/api/wine-images$',      '/api/wine_images'),
    (r'^/api/proposed-image$',   '/api/proposed_image'),
    (r'^/api/fetch-suckling$',   '/api/fetch_suckling'),
    (r'^/api/scan-wine-label$',  '/api/scan_wine_label'),
    (r'^/api/set-image$',        '/api/image_input?mode=url'),
    (r'^/api/upload-image$',     '/api/image_input?mode=data'),
    (r'^/api/confirm-proposed$', '/api/proposed_action?action=confirm'),
    (r'^/api/discard-proposed$', '/api/proposed_action?action=discard'),
    (r'^/api/find-suppliers$',   '/api/find_suppliers'),
]

def _rewrite(path):
    parsed = urlparse(path)
    for pattern, dest in REWRITES:
        if re.match(pattern, parsed.path):
            dp = urlparse(dest)
            q = dp.query
            if parsed.query:
                q = (q + '&' + parsed.query) if q else parsed.query
            return dp.path + ('?' + q if q else '')
    return path

def _load_api_handler(path_only):
    module_name = path_only.lstrip('/').replace('/', '.')  # api.auth
    try:
        mod = importlib.import_module(module_name)
        return getattr(mod, 'handler', None)
    except Exception as e:
        print(f'  [dev] module laden mislukt ({module_name}): {e}')
        return None


class DevHandler(SimpleHTTPRequestHandler):

    def _dispatch(self):
        self.path = _rewrite(self.path)
        parsed = urlparse(self.path)

        if parsed.path.startswith('/api/'):
            cls = _load_api_handler(parsed.path)
            if cls:
                # Swap de klasse op de bestaande, al-geïnitialiseerde handler.
                # Alle HTTP-state (request_version, headers, rfile, wfile) blijft intact.
                method_name = f'do_{self.command}'
                self.__class__ = cls
                method = getattr(self, method_name, None)
                if method:
                    method()
                else:
                    self.send_error(405)
                return
            self.send_error(404, f'API niet gevonden: {parsed.path}')
            return

        # Statische bestanden: herschrijf / naar index.html
        if parsed.path in ('', '/'):
            self.path = '/index.html'
        SimpleHTTPRequestHandler.do_GET(self)

    def _method_not_allowed(self):
        self.send_error(405)

    def do_GET(self):    self._dispatch()
    def do_POST(self):   self._dispatch()
    def do_PATCH(self):  self._dispatch()
    def do_DELETE(self): self._dispatch()
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PATCH,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def translate_path(self, path):
        # Serveer bestanden altijd vanuit BASE_DIR
        parsed = urlparse(path)
        p = parsed.path.lstrip('/')
        return os.path.join(BASE_DIR, p) if p else os.path.join(BASE_DIR, 'index.html')

    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path} → {fmt % args}')


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    os.chdir(BASE_DIR)
    server = HTTPServer(('0.0.0.0', port), DevHandler)
    print(f'Dev-server → http://localhost:{port}')
    print('Ctrl+C om te stoppen.\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nGestopt.')
