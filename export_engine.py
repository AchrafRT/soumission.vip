from pathlib import Path
import zipfile, time, json, shutil, tempfile, os
from storage import Store, APP_ROOT

EXCLUDE_PARTS={'.git','.venv','__pycache__','exports','snapshots','patched','failed','commit'}
EXCLUDE_FILES={'payment_secrets.json','sessions.txt','audit.txt','runtime.txt'}
RUNTIME_DATA={'users.json','homeowners.json','employees.json','invites.json','quotes.json'}

def _should_skip(rel:Path):
    if any(p in EXCLUDE_PARTS for p in rel.parts): return True
    if rel.name in EXCLUDE_FILES: return True
    if rel.parts[:2]==('data','private'): return True
    return False

def create_deployable(store:Store):
    outdir=APP_ROOT/'exports'; outdir.mkdir(exist_ok=True)
    stamp=time.strftime('%Y%m%d_%H%M%S'); out=outdir/f'DirectoryForge_deployable_{stamp}.zip'
    current_files=['config.json','service_tree.json','locations.json','businesses.json','jobs.json','analytics.json']
    # Deployment-safe source archive. Runtime auth/private data stays out.
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in APP_ROOT.rglob('*'):
            if not p.is_file(): continue
            rel=p.relative_to(APP_ROOT)
            if _should_skip(rel) or rel.parts[0]=='data': continue
            # These seed files are replaced below with the running version's current public state.
            if len(rel.parts)>=2 and rel.parts[0]=='seed' and rel.name in current_files: continue
            z.write(p,rel)
        # Seed current editable public configuration/tree/content, but not credentials/client private records.
        for name in current_files:
            src=store.root/name
            if src.exists(): z.write(src,Path('seed')/name)
    return out

def create_full_backup(store:Store):
    outdir=APP_ROOT/'exports'; outdir.mkdir(exist_ok=True)
    stamp=time.strftime('%Y%m%d_%H%M%S'); out=outdir/f'DirectoryForge_full_backup_{stamp}.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in APP_ROOT.rglob('*'):
            if not p.is_file(): continue
            rel=p.relative_to(APP_ROOT)
            if any(x in rel.parts for x in ['.git','.venv','__pycache__','exports','snapshots']): continue
            if rel.parts[:2]==('data','private'): continue
            z.write(p,rel)
        for p in store.root.rglob('*'):
            if p.is_file() and 'private' not in p.parts:
                z.write(p,Path('_BACKUP_DATA')/p.relative_to(store.root))
    return out

def extract_all(store:Store):
    return {'deployable_zip':str(create_deployable(store)),'backup_zip':str(create_full_backup(store))}
