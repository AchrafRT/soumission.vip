from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json, os, mimetypes
from app_logic import DirectoryAPI

ROOT=Path(__file__).resolve().parent; INDEX=ROOT/'frontend'/'index.html'; EXPORT_ROOT=(ROOT/'exports').resolve(); API=DirectoryAPI(); MANIFEST=json.loads((ROOT/'FOUNDATION_MANIFEST.json').read_text(encoding='utf-8'))
class Handler(BaseHTTPRequestHandler):
    def _send(self,code,body,ctype='application/json; charset=utf-8'):
        raw=body if isinstance(body,bytes) else body.encode('utf-8'); self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/brand-logo.png': return self._send(200,(ROOT/'assets'/'soumission-vip-logo.png').read_bytes(),'image/png')
        if path=='/health': return self._send(200,json.dumps({'ok':True,'service':MANIFEST.get('name'),'version':MANIFEST.get('version')}))
        if path.startswith('/exports/'):
            # Private operator artifacts are never served by the public HTTP surface.
            return self._send(404,'not found','text/plain')
        return self._send(200,INDEX.read_bytes(),'text/html; charset=utf-8')
    def do_POST(self):
        if urlparse(self.path).path!='/api/call': return self._send(404,json.dumps({'ok':False,'error':'Not found'}))
        try:
            n=int(self.headers.get('Content-Length','0'));
            if n>12*1024*1024: return self._send(413,json.dumps({'ok':False,'error':'Request too large'}))
            req=json.loads(self.rfile.read(n) or b'{}'); out=API.call(req.get('method',''),req.get('payload') or {},req.get('token'))
            self._send(200,json.dumps(out,ensure_ascii=False))
        except Exception as e: self._send(500,json.dumps({'ok':False,'error':str(e)}))
    def log_message(self,fmt,*args): print('[web]',fmt%args)

def run(host=None,port=None):
    host=host or os.environ.get('HOST','0.0.0.0'); port=int(port or os.environ.get('PORT','8765')); print(f'Soumission.VIP server: http://{host}:{port}'); ThreadingHTTPServer((host,port),Handler).serve_forever()
if __name__=='__main__': run()
