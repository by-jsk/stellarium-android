#!/usr/bin/env python3
"""Preserve Qt's already aligned FFmpeg binary while packaging the APK."""
from pathlib import Path
import os

root=Path(__file__).resolve().parents[1]
sdk=Path(os.environ['QT_ROOT_DIR'])
template=sdk/'src/android/templates/build.gradle'
text=template.read_text(encoding='utf-8')
assert text.count('android {')==1,'Qt Android Gradle template changed'
# NDK stripping rewrites the segments added by Qt's FFmpeg dependency fix-up.
# The vendor library is already stripped and supports 16-KiB memory pages.
text=text.replace('android {','''android {
    packaging {
        jniLibs {
            keepDebugSymbols += ['**/libavformat.so']
        }
    }
''',1)
notice='// Derived from the Qt Android template; Qt Company and contributors.\n// Modified for by-jsk/Stellar Touch on 2026-11-25 to preserve FFmpeg ELF layout.\n'
(root/'engine/android/build.gradle').write_text(notice+text,encoding='utf-8',newline='\n')
print('Qt Gradle template prepared: retain the original aligned libavformat.so')
