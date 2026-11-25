#!/usr/bin/env python3
"""Reject incomplete native APKs before installing or publishing them."""
import json
import hashlib
import struct
import sys
import zipfile
from pathlib import Path

with zipfile.ZipFile(sys.argv[1]) as apk:
    files = set(apk.namelist())
    required = {
        'assets/data/default_cfg.ini',
        'assets/data/ssystem_major.ini',
        'assets/data/ssystem_minor.ini',
        'assets/data/base_locations.bin',
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
    cities=apk.read('assets/data/base_locations.bin')
    assert 10000<struct.unpack_from('>I',cities)[0]<100000,'Offline city database must be unpacked by AAPT'
    assert 'Seoul, Eastern Asia'.encode('utf-16be') in cities
    for lang in ('ko', 'ja', 'zh_CN', 'es', 'ru'):
        assert any(p.startswith('assets/translations/stellarium/') and p.endswith('/'+lang+'.qm') for p in files), lang
    strings = json.loads(apk.read('assets/mobile-i18n.json'))
    assert set(strings) == {'ko', 'en', 'ja', 'zh', 'es', 'ru'}
    libraries=0
    for path in sorted(p for p in files if p.endswith('.so')):
        with apk.open(path) as library:
            header=library.read(64)
            assert header[:6]==b'\x7fELF\x02\x01',path
            assert struct.unpack_from('<H',header,18)[0]=={'arm64-v8a':183,'x86_64':62}[sys.argv[2]],f'Wrong native ABI: {path}'
            offset=struct.unpack_from('<Q',header,32)[0]
            stride,count=struct.unpack_from('<HH',header,54)
            library.seek(offset);segments=library.read(stride*count)
            for i in range(count):
                segment=struct.unpack_from('<IIQQQQQQ',segments,i*stride)
                if segment[0]==1:
                    assert segment[7]>=16384 and segment[2]%16384==segment[3]%16384,f'Native library lacks 16-KiB page support: {path}'
        libraries+=1
    if len(sys.argv)>3:
        original=(Path(sys.argv[3])/'lib/libavformat.so').read_bytes()
        bundled=apk.read(f'lib/{sys.argv[2]}/libavformat.so')
        assert hashlib.sha256(original).digest()==hashlib.sha256(bundled).digest(),'Packaging must preserve Qt FFmpeg libavformat.so without stripping'
    print(f'16-KiB ELF page alignment verified for all {libraries} native libraries')
    print(f'APK content verified: {len(files)} entries; {Path(sys.argv[1]).stat().st_size:,} bytes')
