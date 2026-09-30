import threading, time, os, socket
from server import run

def free_port(preferred=8765):
    s=socket.socket();
    try: s.bind(('127.0.0.1',preferred)); return preferred
    except OSError:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]
    finally: s.close()

def main():
    port=free_port(); os.environ['PORT']=str(port); os.environ['HOST']='127.0.0.1'
    th=threading.Thread(target=run,args=('127.0.0.1',port),daemon=True); th.start(); time.sleep(.35)
    try: import webview
    except ImportError: raise SystemExit('pywebview is not installed. Run Install_Local.bat first.')
    webview.create_window('ROOT — DirectoryForge Owner Console',f'http://127.0.0.1:{port}/admin',width=1440,height=900,min_size=(1080,700))
    webview.start(debug=os.environ.get('DIRECTORYFORGE_DEBUG')=='1')
if __name__=='__main__': main()
