# Source and third-party notices

Stellar Touch is an independent modification of Stellarium. Copyright remains
with the original contributors; see the bundled CREDITS.md, COPYING, individual
source headers, sky-culture index.json files and data credits. The integrated
APK is conveyed under GPLv3, using the upstream GPL-2.0-or-later permission.

The matching release source archive contains the modified engine, this mobile
layer, build scripts, pinned revisions and downloaded CMake dependency sources.
It contains no signing keys. See https://github.com/by-jsk/stellarium-android
and the matching source asset alongside the APK in
https://github.com/by-jsk/app-downloads/releases .

The following unmodified platform components have corresponding source and
build instructions available from their original public distribution servers:

* Qt 6.8.3: Copyright The Qt Company Ltd. and contributors. Qt Charts uses GPLv3
  in this build. Other used Qt modules permit GPLv3 and/or LGPLv3. Full source:
  https://download.qt.io/archive/qt/6.8/6.8.3/single/ . The source includes each
  module's LICENSES directory and third-party attribution files. Build recipes:
  https://github.com/qt/qt5/tree/v6.8.3/coin/provisioning .
* FFmpeg n7.1: Copyright the FFmpeg developers and individual contributors.
  Qt's prebuilt multimedia backend is LGPL-2.1-or-later and includes additional
  permissive notices. Corresponding source, including all notices:
  https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n7.1.tar.gz . Qt attribution:
  https://github.com/qt/qtmultimedia/blob/v6.8.3/src/3rdparty/ffmpeg/qt_attribution.json .
* Android OpenSSL binaries and build scripts are pinned to KDAB's
  b71f1470962019bd89534a2919f5925f93bc5779 revision. OpenSSL 3 uses Apache-2.0;
  KDAB's integration has its own retained notices. Exact build script, patches,
  source download versions and bundled license files:
  https://github.com/KDAB/android_openssl/tree/b71f1470962019bd89534a2919f5925f93bc5779 .
* Android NDK 26.1.10909125 includes LLVM libc++, under Apache-2.0 with LLVM
  exceptions and retained notices. Sources and rebuilding information:
  https://android.googlesource.com/toolchain/llvm-project/ and
  https://android.googlesource.com/platform/ndk/ .

QXlsx, md4c, NLopt, FastFloat and Stellarium's bundled external code retain their
original licenses. The engine's CMake files pin downloads and checksums; their
downloaded source trees are included in the matching release source archive.
Copies of discovered engine/dependency license and notice files are also
bundled under assets/third-party-licenses/.

Data files are independent works and keep their individual licenses. No source
or paid data from the commercial Stellarium Mobile product is used. There is no
claim of affiliation with its developer or with the Stellarium project.
