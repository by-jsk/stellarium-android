#!/usr/bin/env python3
"""Start the real native engine on an emulator and collect its smoke report and screenshots."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from PIL import Image

out = Path('release/smoke')
out.mkdir(parents=True, exist_ok=True)

def adb(*args, binary=False):
    return subprocess.check_output(['adb', *args], text=not binary)

subprocess.run(['adb', 'install', '-r', sys.argv[1]], check=True)
adb('logcat', '-c')
started = time.monotonic()
adb('shell', 'am', 'start', '-W', '-n', 'org.byjsk.stellartouch/org.byjsk.stellartouch.StellarActivity', '--ez', 'stellarSmokeTest', 'true')
deadline = time.monotonic() + 150
report = None
ready_seconds = None
while time.monotonic() < deadline:
    logs = adb('logcat', '-d', '-v', 'brief')
    (out/'logcat.txt').write_text(logs, encoding='utf-8')
    if ready_seconds is None and 'STELLAR_TOUCH_READY' in logs:
        ready_seconds=round(time.monotonic()-started,2)
    match = re.search(r'STELLAR_SMOKE_DONE (\{[^\n]*\})', logs)
    if match:
        report = json.loads(match[1]); break
    if 'Fatal signal' in logs or 'FATAL EXCEPTION' in logs:
        raise SystemExit('Native Android app crashed: see logcat.txt')
    time.sleep(3)
time.sleep(1)
(out/'settings-ko.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
assert report is not None, 'Native smoke report timed out; see logcat.txt'
assert report['passed'], report
report['emulator_ready_seconds_upper_bound']=ready_seconds
(out/'memory.txt').write_text(adb('shell','dumpsys','meminfo','org.byjsk.stellartouch'),encoding='utf-8')
# Read the actual rendered screen. A black screen alone must not pass.
image=Image.open(out/'settings-ko.png').convert('RGB')
image=image.crop((0,60,image.width,image.height-100))
pixels=list(image.getdata())
colored=sum(1 for r,g,b in pixels if g>6 or b>6)
red=sum(1 for r,g,b in pixels if r>25 and g<7 and b<7)
report['night_non_red_fraction']=round(colored/len(pixels),6)
report['night_visible_red_pixels']=red
assert colored/len(pixels)<0.005 and red>200,'Night mode must render visible pure red controls'
# Close the real settings panel through Back, then capture the rendered sky.
adb('shell', 'input', 'keyevent', '4')
time.sleep(2)
(out/'sky-ko.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
(out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
