#!/usr/bin/env python3
"""Source-contract checks, run before compiling the native Android app."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
strings = json.loads((root / 'mobile/i18n.json').read_text(encoding='utf-8'))
assert set(strings) == {'ko', 'en', 'ja', 'zh', 'es', 'ru'}
for language, messages in strings.items():
    assert set(messages) == set(strings['en']), language
    assert all(isinstance(v, str) and v.strip() for v in messages.values()), language
    assert len(messages['guide'].splitlines()) == 8, language
manifest = ET.parse(root / 'android/AndroidManifest.xml').getroot()
ns = '{http://schemas.android.com/apk/res/android}'
permissions = {p.attrib[ns+'name'] for p in manifest.findall('uses-permission')}
assert not any('EXTERNAL_STORAGE' in p for p in permissions)
assert manifest.attrib['package'] == json.loads((root/'version.json').read_text())['packageId']
assert 'android.permission.REQUEST_INSTALL_PACKAGES' in permissions
assert manifest.find('application').attrib[ns+'usesCleartextTraffic']=='false'
java=(root/'android/src/org/byjsk/stellartouch/StellarActivity.java').read_text(encoding='utf-8')
assert 'private static final boolean CI_FIXTURE = false;' in java
print('Six complete mobile languages, eight-step guides, package identity and minimal permissions: PASS')
