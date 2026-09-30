from storage import Store
import secrets, json, time

class SessionStore:
    def __init__(self, store:Store): self.store=store
    @property
    def path(self): return self.store.runtime/'sessions.txt'
    def _read(self):
        out=[]
        try:
            for line in self.path.read_text(encoding='utf-8').splitlines():
                try:
                    row=json.loads(line)
                    if row.get('expires',0)>time.time(): out.append(row)
                except: pass
        except: pass
        return out
    def create(self,user_id, kind='user', hours=24):
        rows=self._read(); token=secrets.token_urlsafe(32)
        rows.append({'token':token,'user_id':user_id,'kind':kind,'expires':time.time()+hours*3600})
        self.path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
        return token
    def get(self,token):
        if not token: return None
        for row in self._read():
            if secrets.compare_digest(row.get('token',''), token): return row
        return None
    def delete(self,token):
        rows=[r for r in self._read() if r.get('token')!=token]
        self.path.write_text('\n'.join(json.dumps(r) for r in rows)+('\n' if rows else ''),encoding='utf-8')
