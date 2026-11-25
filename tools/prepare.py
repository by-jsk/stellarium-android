#!/usr/bin/env python3
"""Reproducibly apply the mobile layer to an exact upstream commit (GPL-2.0-or-later)."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'source.lock.json').read_text())

def replace(path, old, new):
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'Upstream context changed: {path}: {old[:90]!r}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--source', type=Path, default=ROOT / 'engine')
    args = parser.parse_args()
    src = args.source.resolve()
    if args.fetch and not src.exists():
        subprocess.run(['git', 'init', str(src)], check=True)
        subprocess.run(['git', '-C', str(src), 'remote', 'add', 'origin', LOCK['repository']], check=True)
        subprocess.run(['git', '-C', str(src), 'fetch', '--depth=1', 'origin', LOCK['commit']], check=True)
        subprocess.run(['git', '-C', str(src), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
    actual = subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != LOCK['commit']:
        raise RuntimeError(f'Expected {LOCK["commit"]}, got {actual}')
    shutil.copytree(ROOT / 'mobile', src / 'src' / 'mobile', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'android', src / 'android', dirs_exist_ok=True)
    version = json.loads((ROOT / 'version.json').read_text())
    manifest = src / 'android' / 'AndroidManifest.xml'
    manifest.write_text(manifest.read_text().replace('@VERSION_CODE@', str(version['versionCode'])).replace('@VERSION_NAME@', version['versionName']), encoding='utf-8')
    shutil.copy(ROOT / 'mobile' / 'i18n.json', src / 'android' / 'assets' / 'mobile-i18n.json')
    replace(src / 'src' / 'CMakeLists.txt', 'SET(stellarium_exe_SRCS main.cpp)',
            'list(APPEND stellarium_lib_SRCS mobile/MobileShell.cpp mobile/MobileShell.hpp)\nSET(stellarium_exe_SRCS main.cpp)')
    cmake_extra = '''
# Stellar Touch: independent mobile package, using the original PC engine.
if(ANDROID)
  set_target_properties(stellarium PROPERTIES
    QT_ANDROID_PACKAGE_NAME org.byjsk.stellartouch
    QT_ANDROID_MIN_SDK_VERSION 28
    QT_ANDROID_TARGET_SDK_VERSION 35
    QT_ANDROID_COMPILE_SDK_VERSION 35
    QT_ANDROID_VERSION_CODE "@CODE@"
    QT_ANDROID_VERSION_NAME "@NAME@")
endif()
'''.replace('@CODE@', str(version['versionCode'])).replace('@NAME@', version['versionName'])
    src_cmake = src / 'src' / 'CMakeLists.txt'
    if '# Stellar Touch:' not in src_cmake.read_text():
        with src_cmake.open('a', encoding='utf-8', newline='\n') as f:
            f.write(cmake_extra)
    # Keep data inside the package. Broad shared-storage access is unnecessary.
    main_cpp = src / 'src' / 'main.cpp'
    replace(main_cpp, '#include <QtCore/private/qjnihelpers_p.h>', '#include "mobile/MobileShell.hpp"')
    text = main_cpp.read_text()
    start = text.index('#ifdef Q_OS_ANDROID\n\tif (!QJniObject::callStaticMethod') if '#ifdef Q_OS_ANDROID\n\tif (!QJniObject::callStaticMethod' in text else -1
    if start >= 0:
        end = text.index('#endif', start) + len('#endif')
        text = text[:start] + '#ifdef Q_OS_ANDROID\n\tMobileShell::prepare();\n#endif' + text[end:]
        main_cpp.write_text(text, encoding='utf-8', newline='\n')
    gui = src / 'src' / 'gui' / 'StelGui.cpp'
    replace(gui, '#include "StelGui.hpp"', '#include "StelGui.hpp"\n#include "mobile/MobileShell.hpp"')
    replace(gui, '\tinitDone = true;\n}', '\tinitDone = true;\n#ifdef Q_OS_ANDROID\n\tnew MobileShell(atopLevelGraphicsWidget);\n#endif\n}')
    dialog = src / 'src' / 'gui' / 'StelDialog.cpp'
    replace(dialog, '#include "StelDialog.hpp"', '#include "StelDialog.hpp"\n#include "mobile/MobileShell.hpp"')
    replace(dialog, '\t\tproxy->setFocus();', '#ifdef Q_OS_ANDROID\n\t\tMobileShell::fitDialog(dialog, proxy);\n#endif\n\t\tproxy->setFocus();')
    print(f'Mobile layer prepared at {src}, upstream {actual}')

if __name__ == '__main__':
    main()
