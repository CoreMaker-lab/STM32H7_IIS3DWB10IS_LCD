"""Verbose bootstrap for the original Qt UI; native crash log stays on disk."""
import os,sys,runpy,traceback,faulthandler,datetime
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    os.chdir(root)
    log=open(root/'startup.log','a',encoding='utf-8',buffering=1)
    faulthandler.enable(file=log,all_threads=True)
    def note(msg):
        text=str(datetime.datetime.now())+' '+msg;print(text,flush=True);log.write(text+'\n')
    try:
        note('Interpreter: '+sys.executable+' | '+sys.version.replace('\n',' '))
        import importlib
        for module in ['numpy','serial','PySide6.QtCore','PySide6.QtWidgets','pyqtgraph']:
            note('Importing '+module)
            importlib.import_module(module)
            note('OK '+module)
        note('Opening original application UI')
        runpy.run_path(str(root/'app.py'),run_name='__main__')
    except SystemExit as e:
        if e.code not in (0,None):note('Application exit code: '+str(e.code))
        return e.code if isinstance(e.code,int) else 0
    except BaseException:
        trace=traceback.format_exc();print(trace,file=sys.stderr,flush=True);log.write(trace);return 1
    finally:
        faulthandler.disable();log.close()
    return 0
if __name__=='__main__':sys.exit(main())
