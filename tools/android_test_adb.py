"""ADB snapshot handling for disposable CI emulators."""
import json
from pathlib import Path
import os
import subprocess
import time
import re

def report_from_log(logs, marker):
    """Read a Qt JSON report, including complete fields before Android's log limit."""
    for line in reversed(logs.splitlines()):
        prefix, separator, payload = line.partition(marker)
        if not separator or not payload.lstrip().startswith('{'):
            continue
        payload = payload.lstrip()
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            # [20261126 by jsk] Qt Android의 1 KiB 줄 절단 시 이미 기록된 완전한 필드만 복구함.
            if marker != 'STELLAR_SMOKE_DONE' or len(line[len(prefix):].encode('utf-8')) < 1023:
                continue
            for match in reversed(list(re.finditer(',', payload))):
                try:
                    report = json.loads(payload[:match.start()] + '}')
                except json.JSONDecodeError:
                    continue
                if type(report.get('passed')) is bool:
                    report['native_log_truncated'] = True
                    return report
                break
    return None


def app_crashed(logs,pid):
    """Google APIs emulator services can crash independently of the tested app."""
    return any(re.search(r'\(\s*'+re.escape(str(pid))+r'\s*\):',line)
               and ('Fatal signal' in line or 'FATAL EXCEPTION' in line)
               for line in logs.splitlines())

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
            folder=Path(os.environ.get('STELLAR_EVIDENCE_DIR','release/smoke'));folder.mkdir(parents=True,exist_ok=True)
            with (folder/'adb-errors.txt').open('a',encoding='utf-8') as file:
                file.write(f'logcat exit {result.returncode}: {result.stderr}\n')
            # Android logcat can return 255 with a partial snapshot if its ring
            # buffer wraps while being read. Keep the real output and poll again.
            if result.stdout:return result.stdout
            time.sleep(1)
            continue
        raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
    raise subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
