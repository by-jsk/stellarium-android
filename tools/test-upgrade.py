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
from android_test_adb import adb

package='org.byjsk.stellartouch'
activity=package+'/'+package+'.StellarActivity'
out=Path(os.environ.get('STELLAR_EVIDENCE_DIR','release/smoke'))
out.mkdir(parents=True,exist_ok=True)
candidate=Path(sys.argv[1]).resolve()
baseline=Path(sys.argv[2]).resolve()

def launch(flag):
    adb('shell','am','force-stop',package)
    adb('logcat','-c')
    adb('shell','am','start','-W','-n',activity,'--ez',flag,'true')

def wait_marker(marker,seconds=150):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        logs=adb('logcat','-d','-v','brief')
        (out/'upgrade-logcat.txt').write_text(logs,encoding='utf-8')
        found=re.search(re.escape(marker)+r' (\{[^\n]*\})',logs)
        if found:return json.loads(found[1])
        if 'Fatal signal' in logs or 'FATAL EXCEPTION' in logs:raise AssertionError('Upgrade fixture crashed')
        time.sleep(2)
    raise AssertionError('Timed out waiting for '+marker)

subprocess.run(['adb','uninstall',package],check=True)
subprocess.run(['adb','install','--no-incremental',str(baseline)],check=True)
launch('stellarSmokeTest')
seed=wait_marker('STELLAR_SMOKE_DONE')
assert seed['passed'],seed
assert 'versionCode=0' in adb('shell','dumpsys','package',package)
adb('shell','appops','set',package,'REQUEST_INSTALL_PACKAGES','allow')
adb('shell','settings','put','global','package_verifier_enable','0')

requests=[]
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,format,*args):
        requests.append(self.path)

with tempfile.TemporaryDirectory(prefix='stellar-upgrade-') as directory:
    folder=Path(directory)
    shutil.copyfile(candidate,folder/'StellarTouch-v0.1.0.apk')
    (folder/'stellar-touch.json').write_text(json.dumps({
        'versionCode':1,'versionName':'0.1.0',
        'apk':'http://10.0.2.2:8765/StellarTouch-v0.1.0.apk',
        'notes':{'en':'Update preservation test','ko':'업데이트 보존 검사'}
    }),encoding='utf-8')
    server=http.server.ThreadingHTTPServer(('0.0.0.0',8765),functools.partial(Handler,directory=directory))
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        launch('stellarUpgradeTest')
        offered=wait_marker('STELLAR_UPDATE_OFFERED')
        (out/'upgrade-offer.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
        adb('shell','input','tap',str(offered['x']),str(offered['y']))
        deadline=time.monotonic()+180
        prompted=False
        while time.monotonic()<deadline:
            installed=adb('shell','dumpsys','package',package)
            if re.search(r'versionCode=1\s',installed):break
            adb('shell','uiautomator','dump','/sdcard/stellar-update-window.xml')
            xml=adb('shell','cat','/sdcard/stellar-update-window.xml')
            (out/'upgrade-installer.xml').write_text(xml,encoding='utf-8')
            for node in ET.fromstring(xml).iter('node'):
                if node.get('text','').lower() in ('install','update','설치','업데이트') and node.get('clickable')=='true':
                    bounds=list(map(int,re.findall(r'\d+',node.attrib['bounds'])))
                    (out/'upgrade-installer.png').write_bytes(adb('exec-out','screencap','-p',binary=True))
                    adb('shell','input','tap',str((bounds[0]+bounds[2])//2),str((bounds[1]+bounds[3])//2))
                    prompted=True
            time.sleep(2)
        else:raise AssertionError('Android package installer did not upgrade to versionCode=1')
        assert prompted,'No system installation confirmation was observed'
        assert '/stellar-touch.json' in requests,'Update screen did not fetch metadata'
        assert '/StellarTouch-v0.1.0.apk' in requests,'DownloadManager did not fetch the APK'
    finally:
        server.shutdown();server.server_close()

launch('stellarSmokeTest')
after=wait_marker('STELLAR_SMOKE_DONE')
assert after['passed'],after
assert after['persisted_language_at_launch']=='ko',after
assert after['persisted_region_at_launch']=='JP',after
report={'passed':True,'previous_versionCode':0,'installed_versionCode':1,
        'metadata_detected':True,'apk_downloaded':True,'system_install_confirmed':prompted,
        'language_preserved':'ko','region_preserved':'JP','same_signer_required':True,
        'fixture':'x86_64 CI key and loopback HTTP; production ARM64 uses HTTPS and its separate stable release key'}
(out/'upgrade-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
