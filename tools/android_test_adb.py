"""ADB snapshot handling for disposable CI emulators."""
from pathlib import Path
import subprocess
import time

def adb(*args,binary=False):
    snapshot=args[0]=='logcat' and '-d' in args
    command=['adb',*args]
    if snapshot:command+=['-t','8000']
    for attempt in range(5 if snapshot else 1):
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              text=not binary,timeout=60,
                              **({} if binary else {'encoding':'utf-8','errors':'replace'}))
        if result.returncode==0:return result.stdout
        if snapshot:
            folder=Path('release/smoke');folder.mkdir(parents=True,exist_ok=True)
            with (folder/'adb-errors.txt').open('a',encoding='utf-8') as file:
                file.write(f'logcat exit {result.returncode}: {result.stderr}\n')
            # Android logcat can return 255 with a partial snapshot if its ring
            # buffer wraps while being read. Keep the real output and poll again.
            if result.stdout:return result.stdout
            time.sleep(1)
            continue
        raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
    raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
