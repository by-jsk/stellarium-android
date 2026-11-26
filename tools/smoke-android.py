#!/usr/bin/env python3
"""Start the real native engine on an emulator and collect its smoke report and screenshots."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from PIL import Image
from android_test_adb import adb,app_crashed,report_from_log
from android_test_pixels import close_control

out = Path(os.environ.get('STELLAR_EVIDENCE_DIR','release/smoke'))
out.mkdir(parents=True, exist_ok=True)

subprocess.run(['adb', 'install', '--no-incremental', '-r', sys.argv[1]], check=True)
adb('shell','settings','put','secure','immersive_mode_confirmations','confirmed')
adb('logcat','-G','16M')
adb('logcat', '-c')
started = time.monotonic()
adb('shell', 'am', 'start', '-W', '-n', 'org.byjsk.stellartouch/org.byjsk.stellartouch.StellarActivity', '--ez', 'stellarSmokeTest', 'true')
app_pid=adb('shell','pidof','org.byjsk.stellartouch').strip().split()[0]
deadline = time.monotonic() + 150
report = None
ready_seconds = None
milestones=set()
while time.monotonic() < deadline:
    logs = adb('logcat', '-d', '-v', 'brief')
    (out/'logcat.txt').write_text(logs, encoding='utf-8')
    for line in logs.splitlines():
        if ('STELLAR_BOOT' in line or 'STELLAR_TOUCH_READY' in line) and line not in milestones:
            print(line,flush=True);milestones.add(line)
    if ready_seconds is None and 'STELLAR_TOUCH_READY' in logs:
        ready_seconds=round(time.monotonic()-started,2)
    report = report_from_log(logs, 'STELLAR_SMOKE_DONE')
    if report is not None:
        break
    if app_crashed(logs,app_pid):
        raise SystemExit('Native Android app crashed: see logcat.txt')
    time.sleep(3)
# Let a full frame reach the software-rendered Android surface after the native
# self-check changes six languages. Its first report can precede presentation.
time.sleep(8)
(out/'settings-ko.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
if report is None:
    (out/'startup-events.txt').write_text(adb('logcat','-b','events','-d','-v','brief'),encoding='utf-8')
    (out/'startup-activity.txt').write_text(adb('shell','dumpsys','activity','exit-info','org.byjsk.stellartouch'),encoding='utf-8')
    # The Google APIs CI emulator supports root; capture stalled native threads.
    subprocess.run(['adb','root'],capture_output=True)
    subprocess.run(['adb','wait-for-device'],check=True)
    lookup=subprocess.run(['adb','shell','pidof','org.byjsk.stellartouch'],capture_output=True,text=True,timeout=15)
    pid=lookup.stdout.strip()
    if pid:
        stacks=subprocess.run(['adb','shell','debuggerd','-b',pid],capture_output=True,text=True)
        (out/'native-stacks.txt').write_text(stacks.stdout+stacks.stderr,encoding='utf-8')
    raise SystemExit('Native smoke report timed out; see logcat.txt and native-stacks.txt')
assert report['passed'], report
package_version = re.search(r'\bversionCode=(\d+)\b', adb('shell','dumpsys','package','org.byjsk.stellartouch'))
assert package_version, 'APK version must be read independently from Android PackageManager'
installed_code = int(package_version[1])
assert report.get('versionCode', installed_code) == installed_code, report
report['versionCode'] = installed_code
report['emulator_ready_seconds_upper_bound']=ready_seconds
report['android_page_size']=int(adb('shell','getconf','PAGESIZE').strip())
if os.environ.get('STELLAR_EXPECT_PAGE_SIZE'):assert report['android_page_size']==int(os.environ['STELLAR_EXPECT_PAGE_SIZE'])
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
# Use the panel's actual accessible close control. Android 16's predictive Back
# can leave the Activity instead of sending the legacy Qt Key_Back event.
adb('shell','uiautomator','dump','/sdcard/stellar-settings-window.xml')
xml=adb('shell','cat','/sdcard/stellar-settings-window.xml')
(out/'settings-window.xml').write_text(xml,encoding='utf-8')
close=[node for node in ET.fromstring(xml).iter('node')
       if any(node.get(key,'') in ('닫기','Close','×') for key in ('text','content-desc'))
       and node.get('clickable')=='true']
if close:
    bounds=list(map(int,re.findall(r'\d+',close[0].attrib['bounds'])))
    x,y=(bounds[0]+bounds[2])//2,(bounds[1]+bounds[3])//2
    report['settings_close_method']='Android accessibility'
else:
    x,y=close_control(Image.open(out/'settings-ko.png'))
    report['settings_close_method']='visible red X on Qt OpenGL surface'
adb('shell','input','tap',str(x),str(y))
time.sleep(5)
(out/'sky-ko.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
sky=Image.open(out/'sky-ko.png').convert('RGB')
sky=sky.crop((0,60,sky.width,sky.height-100))
assert sum(1 for r,g,b in sky.getdata() if g>6 or b>6)/(sky.width*sky.height)<0.005,'Closing the panel must keep the red sky Activity visible'
# [20261126 by jsk] 메뉴와 지평선 외곽을 제외한 실제 하늘 화면이 검은색으로만 렌더링되는지 확인함.
sky_center = sky.crop((sky.width//4, sky.height//5, sky.width*3//4, sky.height*4//5))
report['rendered_sky_center_red_pixels'] = sum(1 for r,g,b in sky_center.getdata() if r>4)
assert report['rendered_sky_center_red_pixels']>100,'The center of the red sky must contain rendered sky pixels'
before=Image.open(out/'settings-ko.png').convert('RGB')
after=Image.open(out/'sky-ko.png').convert('RGB')
changed=sum(abs(a[0]-b[0])>4 for a,b in zip(before.getdata(),after.getdata()))
assert changed>10000,'Tapping the real close button must visibly remove the settings panel'
report['settings_close_changed_pixels']=changed
report['rendered_settings_close_control']=True
(out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
