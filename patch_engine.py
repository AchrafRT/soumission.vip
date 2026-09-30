from pathlib import Path
import subprocess, sys, os, shutil, time, zipfile

APP_ROOT=Path(__file__).resolve().parent
PATCH_AREAS=[APP_ROOT/'Patch', APP_ROOT/'Renovation']

def _snapshot(area):
    out=area/'snapshots'/f'prepatch_{time.strftime("%Y%m%d_%H%M%S")}.zip'; out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in APP_ROOT.rglob('*'):
            if p.is_file() and not any(x in p.parts for x in ['exports','snapshots','__pycache__','.git']):
                z.write(p,p.relative_to(APP_ROOT))
    return out

def process_patches():
    results=[]
    for area in PATCH_AREAS:
        for d in ['inbox','patched','failed','snapshots']: (area/d).mkdir(parents=True,exist_ok=True)
        primary=area/'patch.txt'
        files=[]
        if primary.exists() and primary.read_text(encoding='utf-8',errors='ignore').strip(): files.append(primary)
        files += sorted([p for p in (area/'inbox').glob('*.txt') if p not in files])
        for p in files:
            stamp=time.strftime('%Y%m%d_%H%M%S')
            snap=_snapshot(area)
            env=os.environ.copy(); env['APP_ROOT']=str(APP_ROOT); env['PATCH_SOURCE']=str(p)
            proc=subprocess.run([sys.executable,str(p)],cwd=str(APP_ROOT),env=env,capture_output=True,text=True,timeout=180)
            rec={'area':area.name,'file':p.name,'ok':proc.returncode==0,'returncode':proc.returncode,'stdout':proc.stdout[-5000:],'stderr':proc.stderr[-5000:],'snapshot':str(snap)}
            target=(area/'patched' if proc.returncode==0 else area/'failed')/f'{stamp}__{p.name}'
            if p==primary:
                shutil.copy2(p,target); p.write_text('',encoding='utf-8')
            else: shutil.move(str(p),str(target))
            results.append(rec)
    return results
