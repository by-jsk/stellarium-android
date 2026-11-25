#!/usr/bin/env python3
"""Reproducibly apply the mobile layer to an exact upstream commit (GPL-2.0-or-later)."""
import argparse
import json
import os
import re
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
    (src / 'src' / 'mobile' / 'MobileVersion.hpp').write_text(
        f'#pragma once\n#define STELLAR_VERSION_CODE {version["versionCode"]}\n'
        f'#define STELLAR_VERSION_NAME "{version["versionName"]}"\n'
        + ('#define STELLAR_CI_FIXTURE\n' if os.getenv('STELLAR_CI_FIXTURE') == '1' else ''), encoding='utf-8')
    manifest = src / 'android' / 'AndroidManifest.xml'
    manifest.write_text(manifest.read_text().replace('@VERSION_CODE@', str(version['versionCode'])).replace('@VERSION_NAME@', version['versionName']), encoding='utf-8')
    if os.getenv('STELLAR_CI_FIXTURE') == '1':
        manifest.write_text(manifest.read_text().replace('android:usesCleartextTraffic="false"', 'android:usesCleartextTraffic="true"'), encoding='utf-8')
        activity=src/'android/src/org/byjsk/stellartouch/StellarActivity.java'
        activity.write_text(activity.read_text().replace('CI_FIXTURE = false', 'CI_FIXTURE = true'), encoding='utf-8')
    (src / 'android' / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / 'mobile' / 'i18n.json', src / 'android' / 'assets' / 'mobile-i18n.json')
    replace(src / 'src' / 'CMakeLists.txt', 'SET(stellarium_exe_SRCS main.cpp)',
            'list(APPEND stellarium_lib_SRCS mobile/MobileShell.cpp mobile/MobileShell.hpp)\nSET(stellarium_exe_SRCS main.cpp)')
    cmake_extra = '''
# Stellar Touch: independent mobile package, using the original PC engine.
if(ANDROID)
  set_target_properties(stellarium PROPERTIES
    QT_ANDROID_PACKAGE_NAME org.byjsk.stellartouch
    QT_ANDROID_MIN_SDK_VERSION 28
    QT_ANDROID_TARGET_SDK_VERSION 36
    QT_ANDROID_COMPILE_SDK_VERSION 36
    QT_ANDROID_VERSION_CODE "@CODE@"
    QT_ANDROID_VERSION_NAME "@NAME@")
endif()
'''.replace('@CODE@', str(version['versionCode'])).replace('@NAME@', version['versionName'])
    src_cmake = src / 'src' / 'CMakeLists.txt'
    if '# Stellar Touch:' in src_cmake.read_text():
        updated=re.sub(r'\n# Stellar Touch:.*?\nendif\(\)\n',lambda _:cmake_extra,src_cmake.read_text(),flags=re.S)
        src_cmake.write_text(updated,encoding='utf-8',newline='\n')
    else:
        with src_cmake.open('a', encoding='utf-8', newline='\n') as f:
            f.write(cmake_extra)
    # Keep data inside the package. Broad shared-storage access is unnecessary.
    main_cpp = src / 'src' / 'main.cpp'
    replace(main_cpp, '#include <QtCore/private/qjnihelpers_p.h>', '#include "mobile/MobileShell.hpp"')
    replace(main_cpp, 'int main(int argc, char **argv)\n{', 'int main(int argc, char **argv)\n{\n\tqWarning("STELLAR_BOOT main");')
    replace(main_cpp, '\tStelApplication app(argc, argv);', '\tqWarning("STELLAR_BOOT before QApplication");\n\tStelApplication app(argc, argv);\n\tqWarning("STELLAR_BOOT QApplication ready");')
    replace(main_cpp, '\tsetlocale(LC_NUMERIC, "C");', '\tqWarning("STELLAR_BOOT font ready");\n\tsetlocale(LC_NUMERIC, "C");')
    replace(main_cpp, '\tStelFileMgr::init();', '\tqWarning("STELLAR_BOOT before files");\n\tStelFileMgr::init();\n\tqWarning("STELLAR_BOOT files ready");')
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
    sky_gui = src / 'src' / 'gui' / 'SkyGui.cpp'
    replace(sky_gui,'#include "SkyGui.hpp"','#include "SkyGui.hpp"\n#include <QApplication>')
    toolbar='\tinfoY = qMax(infoY, qreal(118+qApp->property("stellarSafeTop").toInt())); // Stellar Touch toolbar clearance\n\tinfoPanel->setTextWidth(qMax(220, StelMainView::getInstance().width()-20));\n\tinfoPanel->setPos(infoX, infoY);'
    legacy=toolbar.replace('118+qApp->property("stellarSafeTop").toInt()','118')
    if legacy in sky_gui.read_text():replace(sky_gui,legacy,toolbar)
    replace(sky_gui,'\tinfoPanel->setPos(infoX, infoY);',toolbar)
    defaults = src / 'cmake' / 'default_cfg.ini.cmake'
    replace(defaults, 'minimum_fps                         = 18', 'minimum_fps                         = 2')
    replace(defaults, 'maximum_fps                         = 10000', 'maximum_fps                         = 60')
    replace(defaults, 'flag_night                          = false', 'flag_night                          = true')
    replace(defaults, 'location                            = auto', 'location                            = Seoul, Eastern Asia')
    replace(defaults, 'Satellites                          = true', 'Satellites                          = false')
    replace(defaults, 'SolarSystemEditor                   = true', 'SolarSystemEditor                   = false')
    view = src / 'src' / 'StelMainView.cpp'
    replace(view, '"uniform sampler2D  u_source;\\n"', '"uniform sampler2D  u_source;\\n"\n\t\t\t\t"uniform mediump float u_nightBrightness;\\n"')
    replace(view, 'vec4(luminance, luminance * 0.3, 0.0, 1.0)', 'vec4(luminance * u_nightBrightness, 0.0, 0.0, 1.0)')
    replace(view, 'program->setUniformValue(vars.source, 0);', 'program->setUniformValue(vars.source, 0);\n\t\tprogram->setUniformValue("u_nightBrightness", GLfloat(qApp->property("stellarNightBrightness").toDouble()));')
    splash = src / 'src' / 'StelSplashScreen.cpp'
    replace(splash, 'const QString titleText = "Stellarium";', 'const QString titleText = "Stellar Touch";')
    replace(splash, 'const QString subtitleText = "stellarium.org";', 'const QString subtitleText = "Stellarium engine / GPL";')
    text = splash.read_text(encoding='utf-8')
    if 'Stellar Touch red startup' not in text:
        text = text.replace('Qt::white', 'QColor(125, 0, 0)')
        text = text.replace('setPixmap(makePixmap(sizeRatio));', '''// Stellar Touch red startup: never show the desktop white splash.
    QImage image = makePixmap(sizeRatio).toImage().convertToFormat(QImage::Format_ARGB32);
    for (int y=0; y<image.height(); ++y) {
        auto line=reinterpret_cast<QRgb*>(image.scanLine(y));
        for(int x=0; x<image.width(); ++x) {const auto c=line[x];line[x]=qRgba(qMax(qRed(c),qMax(qGreen(c),qBlue(c)))/3,0,0,qAlpha(c));}
    }
    setPixmap(QPixmap::fromImage(image));''')
        splash.write_text(text, encoding='utf-8', newline='\n')
    print(f'Mobile layer prepared at {src}, upstream {actual}')

if __name__ == '__main__':
    main()
