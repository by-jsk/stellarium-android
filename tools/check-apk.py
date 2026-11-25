#!/usr/bin/env python3
"""Reject incomplete native APKs before installing or publishing them."""
import json
import sys
import zipfile
from pathlib import Path

with zipfile.ZipFile(sys.argv[1]) as apk:
    files = set(apk.namelist())
    required = {
        'assets/data/default_cfg.ini',
        'assets/data/ssystem_major.ini',
        'assets/data/ssystem_minor.ini',
        'assets/stars/hip_gaia3/stars_0_0v0_21.cat',
        'assets/stars/hip_gaia3/defaultStarsConfig.json',
        'assets/skycultures/modern/index.json',
        'assets/mobile-i18n.json',
        'assets/COPYING',
        'assets/LICENSE-GPL-3.0.txt',
        f'lib/{sys.argv[2]}/libstellarium_{sys.argv[2]}.so',
    }
    missing = required-files
    assert not missing, f'Incomplete engine APK: {sorted(missing)}'
    for lang in ('ko', 'ja', 'zh_CN', 'es', 'ru'):
        assert any(p.startswith('assets/translations/stellarium/') and p.endswith('/'+lang+'.qm') for p in files), lang
    strings = json.loads(apk.read('assets/mobile-i18n.json'))
    assert set(strings) == {'ko', 'en', 'ja', 'zh', 'es', 'ru'}
    print(f'APK content verified: {len(files)} entries; {Path(sys.argv[1]).stat().st_size:,} bytes')
