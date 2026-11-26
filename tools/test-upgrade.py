#!/usr/bin/env python3
"""Exercise the real update screen, DownloadManager and system installer on the CI emulator.

The x86-only fixture uses a local HTTP server. Production ARM64 accepts only the
public HTTPS release URL; neither its key nor any private source is used here.
"""
import functools
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from android_test_adb import adb,app_crashed,report_from_log

version=json.loads((Path(__file__).resolve().parents[1]/'version.json').read_text())
code=version['versionCode']
# [20261126 by jsk] 앱의 CI 전용 허용 주소를 사용하고, 파일에는 최신 후보 APK를 제공함.
apk_name='StellarTouch-v0.1.0.apk'
package=version['packageId']
activity=package+'/'+package+'.StellarActivity'
out=Path(os.environ.get('STELLAR_EVIDENCE_DIR','release/smoke'))
out.mkdir(parents=True,exist_ok=True)
candidate=Path(sys.argv[1]).resolve()
baseline=Path(sys.argv[2]).resolve()

def launch(flag):
    global app_pid
    adb('shell','am','force-stop',package)
    # PackageManager can report the new version before the old Activity/process
    # has finished being removed. Do not deliver the test intent to that Activity.
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        process=subprocess.run(['adb','shell','pidof',package],capture_output=True,text=True)
        if not process.stdout.strip():break
        time.sleep(0.5)
    else:raise AssertionError('Previous app process did not stop')
    adb('logcat','-c')
    print(adb('shell','am','start','-W','-n',activity,'--ez',flag,'true'),flush=True)
    app_pid=adb('shell','pidof',package).strip().split()[0]

def wait_marker(marker,seconds=150):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        logs=adb('logcat','-d','-v','brief')
        (out/'upgrade-logcat.txt').write_text(logs,encoding='utf-8')
        report=report_from_log(logs,marker)
        if report is not None:return report
        if app_crashed(logs,app_pid):raise AssertionError('Upgrade fixture crashed')
        time.sleep(2)
    raise AssertionError('Timed out waiting for '+marker)

subprocess.run(['adb','uninstall',package],check=True)
subprocess.run(['adb','install','--no-incremental',str(baseline)],check=True)
launch('stellarSmokeTest')
seed=wait_marker('STELLAR_SMOKE_DONE')
assert seed['passed'],seed
print('Previous-version engine and independent Korean/Japan preferences verified',flush=True)
assert re.search(rf'versionCode={code-1}\s',adb('shell','dumpsys','package',package))
adb('shell','appops','set',package,'REQUEST_INSTALL_PACKAGES','allow')
adb('shell','settings','put','global','package_verifier_enable','0')

requests=[]
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,format,*args):
        requests.append(self.path)

with tempfile.TemporaryDirectory(prefix='stellar-upgrade-') as directory:
    folder=Path(directory)
    shutil.copyfile(candidate,folder/apk_name)
    (folder/'stellar-touch.json').write_text(json.dumps({
        'versionCode':code,'versionName':version['versionName'],
        'apk':f'http://10.0.2.2:8765/{apk_name}',
        'notes':{'en':'Update preservation test','ko':'업데이트 보존 검사'}
    }),encoding='utf-8')
    server=http.server.ThreadingHTTPServer(('0.0.0.0',8765),functools.partial(Handler,directory=directory))
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        launch('stellarUpgradeTest')
        # [20261126 by jsk] 설정 화면의 업데이트 버튼을 눌러 터치 처리 중 화면 교체 오류를 검증함.
        update_button=wait_marker('STELLAR_UPDATE_SETTINGS_BUTTON')
        adb('shell','input','tap',str(update_button['x']),str(update_button['y']))
        offered=wait_marker('STELLAR_UPDATE_OFFERED')
        print('Settings update button opened the update screen and offered the candidate',flush=True)
        (out/'upgrade-offer.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
        adb('shell','input','tap',str(offered['x']),str(offered['y']))
        deadline=time.monotonic()+180
        prompted=False
        completed=False
        while time.monotonic()<deadline:
            installed=adb('shell','dumpsys','package',package)
            adb('shell','uiautomator','dump','/sdcard/stellar-update-window.xml')
            xml=adb('shell','cat','/sdcard/stellar-update-window.xml')
            (out/'upgrade-installer.xml').write_text(xml,encoding='utf-8')
            nodes=list(ET.fromstring(xml).iter('node'))
            finished=[node for node in nodes if node.get('package')=='com.google.android.packageinstaller'
                      and node.get('text','').lower() in ('done','open','완료','열기')
                      and node.get('enabled')=='true' and node.get('clickable')=='true']
            if re.search(rf'versionCode={code}\s',installed) and finished:
                (out/'upgrade-completed.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
                completed=True
                for node in finished:
                    if node.get('text','').lower() in ('done','완료'):
                        bounds=list(map(int,re.findall(r'\d+',node.attrib['bounds'])))
                        adb('shell','input','tap',str((bounds[0]+bounds[2])//2),str((bounds[1]+bounds[3])//2))
                        break
                print(f'Android installer completed; versionCode={code} confirmed',flush=True)
                break
            for node in nodes:
                if node.get('text','').lower() in ('install','update','설치','업데이트') and node.get('clickable')=='true' and node.get('enabled')=='true':
                    bounds=list(map(int,re.findall(r'\d+',node.attrib['bounds'])))
                    (out/'upgrade-installer.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
                    adb('shell','input','tap',str((bounds[0]+bounds[2])//2),str((bounds[1]+bounds[3])//2))
                    prompted=True
            time.sleep(2)
        else:raise AssertionError(f'Android package installer did not upgrade to versionCode={code}')
        assert prompted,'No system installation confirmation was observed'
        assert completed,'The system installer must finish before relaunching the app'
        assert '/stellar-touch.json' in requests,'Update screen did not fetch metadata'
        assert f'/{apk_name}' in requests,'DownloadManager did not fetch the APK'
    finally:
        server.shutdown();server.server_close()

launch('stellarSmokeTest')
after=wait_marker('STELLAR_SMOKE_DONE')
assert after['passed'],after
assert after['persisted_language_at_launch']=='ko',after
assert after['persisted_region_at_launch']=='JP',after
report={'passed':True,'previous_versionCode':code-1,'installed_versionCode':code,
        'opened_from_settings_button':True,
        'metadata_detected':True,'apk_downloaded':True,'system_install_confirmed':prompted,
        'system_install_completed':completed,
        'language_preserved':'ko','region_preserved':'JP','same_signer_required':True,
        'fixture':'x86_64 CI key and loopback HTTP; production ARM64 uses HTTPS and its separate stable release key'}
(out/'upgrade-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
