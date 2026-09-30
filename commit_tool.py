from pathlib import Path
import zipfile, tempfile, hashlib, json, shutil, time, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import Store
from export_engine import create_deployable
ROOT=Path(__file__).resolve().parents[1]

def hashes(folder):
    out={}
    for p in folder.rglob('*'):
        if p.is_file(): out[str(p.relative_to(folder)).replace('\\','/')]=hashlib.sha256(p.read_bytes()).hexdigest()
    return out

def main():
    print('DirectoryForge Commit Builder')
    raw=input('Path to the latest ONLINE deployable .zip: ').strip().strip('"')
    oldzip=Path(raw)
    if not oldzip.exists() or oldzip.suffix.lower()!='.zip': raise SystemExit('That ZIP does not exist.')
    newzip=create_deployable(Store())
    stamp=time.strftime('%Y%m%d_%H%M%S'); out=ROOT/'Commits'/'commit'/stamp; out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        a=Path(td)/'old'; b=Path(td)/'new'; a.mkdir(); b.mkdir()
        with zipfile.ZipFile(oldzip) as z:z.extractall(a)
        with zipfile.ZipFile(newzip) as z:z.extractall(b)
        ah,bh=hashes(a),hashes(b); added=sorted(bh.keys()-ah.keys()); deleted=sorted(ah.keys()-bh.keys()); changed=sorted(k for k in ah.keys()&bh.keys() if ah[k]!=bh[k])
        files=out/'files'
        for rel in added+changed:
            dst=files/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(b/rel,dst)
        manifest={'created_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'base_zip':str(oldzip),'current_zip':str(newzip),'added':added,'changed':changed,'deleted':deleted}
        (out/'commit_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        (out/'DELETE.txt').write_text('\n'.join(deleted),encoding='utf-8')
        msg=f'DirectoryForge update: {len(added)} added, {len(changed)} changed, {len(deleted)} deleted'
        (out/'COMMIT_MESSAGE.txt').write_text(msg+'\n',encoding='utf-8')
        with zipfile.ZipFile(out/'commit_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
            for p in out.rglob('*'):
                if p.is_file() and p.name!='commit_bundle.zip': z.write(p,p.relative_to(out))
    print('\nCommit bundle created:')
    print(out)
    print(msg)
if __name__=='__main__': main()
