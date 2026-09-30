from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, sysconfig
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VENV=ROOT/'.venv'
REQ=ROOT/'requirements-local.txt'


def run(cmd, **kw):
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def inspect_python(exe):
    code=("import json,sys,sysconfig; "
          "print(json.dumps({'exe':sys.executable,'version':list(sys.version_info[:3]),"
          "'free_threaded':bool(sysconfig.get_config_var('Py_GIL_DISABLED')),'impl':sys.implementation.name}))")
    try:
        r=run([str(exe),'-c',code],timeout=8)
        if r.returncode: return None
        d=json.loads(r.stdout.strip().splitlines()[-1])
        d['source']=str(exe)
        return d
    except Exception:
        return None


def launcher_candidates():
    items=[]
    # Windows Python launcher is the most reliable way to find side-by-side installs.
    if shutil.which('py'):
        r=run(['py','-0p'])
        for line in r.stdout.splitlines():
            line=line.strip()
            if not line: continue
            # Typical lines: -V:3.12 * C:\Python312\python.exe
            path=line.split()[-1]
            if path.lower().endswith('python.exe'): items.append(path)
        for tag in ('3.12','3.11','3.13','3.14'):
            r=run(['py',f'-{tag}','-c','import sys;print(sys.executable)'])
            if r.returncode==0 and r.stdout.strip(): items.append(r.stdout.strip().splitlines()[-1])
    for name in ('python','python3'):
        p=shutil.which(name)
        if p: items.append(p)
    items.append(sys.executable)
    seen=[]
    for x in items:
        if x and str(x).lower() not in [str(y).lower() for y in seen]: seen.append(x)
    return seen


def compatible(d):
    if not d or d.get('impl')!='cpython' or d.get('free_threaded'): return False
    major,minor,_=d.get('version',[0,0,0])
    return major==3 and 10<=minor<=14


def choose_python():
    found=[]
    for c in launcher_candidates():
        d=inspect_python(c)
        if d: found.append(d)
    usable=[d for d in found if compatible(d)]
    # Prefer normal CPython 3.12, then 3.11, then 3.13, then other compatible builds.
    rank={12:0,11:1,13:2,14:3,10:4}
    usable.sort(key=lambda d:(rank.get(d['version'][1],9),-d['version'][2]))
    return (usable[0] if usable else None),found


def venv_python():
    return VENV/'Scripts'/'python.exe' if os.name=='nt' else VENV/'bin'/'python'


def venv_ok():
    p=venv_python()
    if not p.exists(): return False
    d=inspect_python(p)
    return bool(d and compatible(d))


def doctor(found=None):
    if found is None: _,found=choose_python()
    print('\nDirectoryForge / root Python Doctor')
    print('='*48)
    if not found:
        print('No Python interpreter was detected.')
    for d in found:
        v='.'.join(map(str,d['version']))
        ft='FREE-THREADED (incompatible with the current pywebview/pythonnet chain)' if d['free_threaded'] else 'standard GIL build'
        ok='OK' if compatible(d) else 'SKIP'
        print(f"[{ok}] Python {v} | {ft}\n     {d['exe']}")
    print('='*48)
    print('Local desktop target: standard CPython 3.12 is preferred.')


def ensure_venv():
    selected,found=choose_python()
    if venv_ok():
        return venv_python()
    if VENV.exists():
        print('Removing incompatible or incomplete .venv ...')
        shutil.rmtree(VENV,ignore_errors=True)
    if not selected:
        doctor(found)
        print('\nNo compatible standard CPython was found.')
        print('Your free-threaded Python can stay installed, but pywebview currently needs a standard build.')
        print('Run Install_Compatible_Python.bat, or install standard CPython 3.12 from python.org, then run this launcher again.')
        raise SystemExit(23)
    exe=selected['exe']
    print(f"Creating .venv with Python {'.'.join(map(str,selected['version']))}: {exe}")
    r=subprocess.run([exe,'-m','venv',str(VENV)])
    if r.returncode: raise SystemExit(r.returncode)
    return venv_python()


def install():
    py=ensure_venv()
    print('Upgrading pip ...')
    if subprocess.run([str(py),'-m','pip','install','--upgrade','pip']).returncode: raise SystemExit(24)
    print('Installing local desktop requirements ...')
    if subprocess.run([str(py),'-m','pip','install','-r',str(REQ)]).returncode: raise SystemExit(25)
    verify="import webview; print('pywebview OK')"
    if subprocess.run([str(py),'-c',verify]).returncode: raise SystemExit(26)
    print('\nLocal environment is ready.')
    return py


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--doctor',action='store_true')
    ap.add_argument('--launch',action='store_true')
    args=ap.parse_args()
    if args.doctor:
        doctor(); return
    py=install()
    if args.launch:
        raise SystemExit(subprocess.run([str(py),str(ROOT/'app.py')],cwd=str(ROOT)).returncode)

if __name__=='__main__': main()
