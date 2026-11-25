#!/usr/bin/env python3
"""Start the real native engine on an emulator and collect its smoke report and screenshots."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

out = Path('release/smoke')
out.mkdir(parents=True, exist_ok=True)

def adb(*args, binary=False):
    return subprocess.check_output(['adb', *args], text=not binary)

subprocess.run(['adb', 'install', '-r', sys.argv[1]], check=True)
adb('logcat', '-c')
adb('shell', 'am', 'start', '-W', '-n', 'org.byjsk.stellartouch/org.byjsk.stellartouch.StellarActivity', '--ez', 'stellarSmokeTest', 'true')
deadline = time.monotonic() + 150
report = None
while time.monotonic() < deadline:
    logs = adb('logcat', '-d', '-v', 'brief')
    (out/'logcat.txt').write_text(logs, encoding='utf-8')
    match = re.search(r'STELLAR_SMOKE_DONE (\{[^\n]*\})', logs)
    if match:
        report = json.loads(match[1]); break
    if 'Fatal signal' in logs or 'FATAL EXCEPTION' in logs:
        raise SystemExit('Native Android app crashed: see logcat.txt')
    time.sleep(3)
(out/'settings-ko.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
assert report is not None, 'Native smoke report timed out; see logcat.txt'
(out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
assert report['passed'], report
# Close the real settings panel through Back, then capture the rendered sky.
adb('shell', 'input', 'keyevent', '4')
time.sleep(2)
(out/'sky-ko.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
print(json.dumps(report, ensure_ascii=False, indent=2))
