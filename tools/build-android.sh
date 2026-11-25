#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${QT_ROOT_DIR:?Set QT_ROOT_DIR to the Android Qt directory}"
: "${QT_HOST_PATH:?Set QT_HOST_PATH to the matching desktop Qt directory}"
: "${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT}"
: "${ANDROID_NDK_ROOT:?Set ANDROID_NDK_ROOT}"
ABI=${ANDROID_ABI:-arm64-v8a}
BUILD="build-$ABI"
export CCACHE_BASEDIR="$PWD/engine"
export CCACHE_DIR="$PWD/.ccache/$ABI"
export CCACHE_SLOPPINESS=pch_defines,time_macros
cmake -S engine -B "$BUILD" -GNinja \
  -DCMAKE_TOOLCHAIN_FILE="$QT_ROOT_DIR/lib/cmake/Qt6/qt.toolchain.cmake" \
  -DQT_HOST_PATH="$QT_HOST_PATH" -DANDROID_SDK_ROOT="$ANDROID_SDK_ROOT" \
  -DANDROID_NDK_ROOT="$ANDROID_NDK_ROOT" -DANDROID_ABI="$ABI" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PWD/stage/$ABI" \
  -DCMAKE_CXX_FLAGS="-Xclang -fno-pch-timestamp" \
  -DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON \
  -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-z,max-page-size=16384" \
  -DQT_NO_GLOBAL_APK_TARGET_PART_OF_ALL=ON \
  -DQt6LinguistTools_DIR="$QT_HOST_PATH/lib/cmake/Qt6LinguistTools" \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DSTELLARIUM_RELEASE_BUILD=0 -DENABLE_TESTING=OFF -DENABLE_SHOWMYSKY=OFF \
  -DENABLE_SPEECH=ON -DENABLE_SCRIPTING=ON -DENABLE_XLSX=ON \
  -DENABLE_NLS=ON -DENABLE_PODIR=ON -DENABLE_QTWEBENGINE=OFF \
  -DENABLE_GPS=OFF -DENABLE_INDI=ON -DGENERATE_PACKAGE_TARGET=OFF
cmake --build "$BUILD" --target src/CMakeFiles/stelMain.dir/mobile/MobileShell.cpp.o --parallel 2
cmake --build "$BUILD" --parallel "${BUILD_JOBS:-3}"
cmake --install "$BUILD"
cp -a "stage/$ABI/share/stellarium/." engine/android/assets/
cp LICENSE engine/android/assets/COPYING
cp LICENSE-GPL-3.0.txt engine/android/assets/LICENSE-GPL-3.0.txt
cp engine/CREDITS.md engine/android/assets/CREDITS.md
python3 tools/package-notices.py "$ABI"
# Maven Central occasionally rate-limits shared CI runners. Retry only deployment;
# compilation and the APK content contract must still succeed.
for attempt in 1 2 3; do
  if cmake --build "$BUILD" --target apk --parallel 2; then break; fi
  if [ "$attempt" = 3 ]; then exit 1; fi
  sleep "$((attempt * 15))"
done
mkdir -p release
find "$BUILD" -name '*release-unsigned.apk' -exec cp '{}' "release/StellarTouch-$ABI-unsigned.apk" \;
test -f "release/StellarTouch-$ABI-unsigned.apk"
python3 tools/check-apk.py "release/StellarTouch-$ABI-unsigned.apk" "$ABI"
ccache --show-stats
