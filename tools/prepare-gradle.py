#!/usr/bin/env python3
"""Prepare the APK's Qt template and patched Android speech wrapper."""
from pathlib import Path
import os

root=Path(__file__).resolve().parents[1]
sdk=Path(os.environ['QT_ROOT_DIR'])
template=sdk/'src/android/templates/build.gradle'
text=template.read_text(encoding='utf-8')
assert text.count('android {')==1,'Qt Android Gradle template changed'
# Compile the patched Java wrapper with the app instead of taking its duplicate
# class from Qt's prebuilt jar. The native Qt speech plugin is still used.
dependencies="implementation fileTree(dir: 'libs', include: ['*.jar', '*.aar'])"
assert text.count(dependencies) == 1, 'Qt Android Gradle dependencies changed'
text=text.replace(dependencies,
    "implementation fileTree(dir: 'libs', include: ['*.jar', '*.aar'], "
    "exclude: ['QtAndroidTextToSpeech.jar'])")
# NDK stripping rewrites the segments added by Qt's FFmpeg dependency fix-up.
# The vendor library is already stripped and supports 16-KiB memory pages.
text=text.replace('android {','''android {
    packaging {
        jniLibs {
            keepDebugSymbols += ['**/libavformat.so']
        }
    }
''',1)
notice=('// Derived from the Qt Android template; Qt Company and contributors.\n'
        '// Modified for Stellar Touch on 2026-11-25 to preserve FFmpeg ELF layout\n'
        '// and on 2026-11-26 to compile the patched Android speech wrapper.\n')
(root/'engine/android/build.gradle').write_text(notice+text,encoding='utf-8',newline='\n')
print('Qt Gradle template prepared: retain the original aligned libavformat.so')
