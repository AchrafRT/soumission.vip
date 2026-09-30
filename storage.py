from pathlib import Path
import os, json, shutil, tempfile, threading, time

APP_ROOT=Path(__file__).resolve().parent
DATA_DIR=Path(os.environ.get('DATA_DIR', APP_ROOT/'data')).resolve()
SEED_DIR=APP_ROOT/'seed'
_LOCK=threading.RLock()

class Store:
    def __init__(self):
        self.root=DATA_DIR
        self.private=self.root/'private'
        self.runtime=self.root/'runtime'
        self.ensure_initialized()

    def ensure_initialized(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.private.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        for src in SEED_DIR.glob('*.json'):
            dst=self.root/src.name
            if not dst.exists(): shutil.copy2(src,dst)
        for name in ['sessions.txt','audit.txt','runtime.txt']:
            p=self.runtime/name
            if not p.exists(): p.write_text('',encoding='utf-8')
        sec=self.private/'payment_secrets.json'
        if not sec.exists(): sec.write_text('{}',encoding='utf-8')

    def path(self,name): return self.root/name
    def load(self,name, default=None):
        with _LOCK:
            p=self.path(name)
            if not p.exists(): return default
            try: return json.loads(p.read_text(encoding='utf-8'))
            except Exception: return default
    def save(self,name,obj):
        with _LOCK:
            p=self.path(name); p.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix=p.name+'.',suffix='.tmp',dir=str(p.parent)); os.close(fd)
            Path(tmp).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(tmp,p)
    def append_runtime(self,name, obj):
        with _LOCK:
            p=self.runtime/name
            line=obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False)
            with p.open('a',encoding='utf-8') as f: f.write(line.rstrip()+'\n')
    def load_private(self): return json.loads((self.private/'payment_secrets.json').read_text(encoding='utf-8') or '{}')
    def save_private(self,obj): (self.private/'payment_secrets.json').write_text(json.dumps(obj,indent=2),encoding='utf-8')
