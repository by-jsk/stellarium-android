# Android verification

The workflow builds the pinned PC engine for arm64-v8a and x86_64. A completed
compile is not an execution test. Release status stays provisional until the
emulator report, rendered screenshots, signing checks and upgrade report pass.

## Artifact checks

`tools/check-apk.py` opens the actual APK and requires the native engine, default
configuration, solar-system data, star catalogue, modern sky culture, five
non-English engine translations, all six mobile languages and license texts.
Building the CMake `ALL` target must not create the APK before installation data
is copied: `QT_NO_GLOBAL_APK_TARGET_PART_OF_ALL=ON` enforces that order.

## Execution and red illumination

`tools/smoke-android.py` installs and launches the real native library on an
Android 16 x86_64 emulator and an Android 15 emulator with 16-KiB memory pages. The engine reports loaded objects (Sun, Moon, Mars,
Sirius and M31), finite celestial positions, time changes, registered actions,
language fallback, separate persisted region/language and Settings entry order
in all six languages. It captures screenshots, logcat, memory and observed FPS.
All native ELF libraries must support 16-KiB pages, and the second emulator's actual page size is checked. The pixel check requires visible red controls and rejects non-red illumination
and a blank black screen. A timeout captures native thread stacks for diagnosis.

The emulator's observed FPS and startup time are diagnostic measurements. They
are not performance measurements on a Galaxy S25 or all supported devices.
Hardware telescope control, every plugin configuration, external services and
physical GPS reception need additional field testing.

## Update preservation

Only the x86 CI fixture defines `STELLAR_CI_FIXTURE`. The distribution ARM64
manifest disallows cleartext HTTP and its Java flag remains a compile-time
`false`. The fixture permits a single emulator loopback server; the normal
release permits the exact public HTTPS release URL.

`tools/fixture-apk.py` changes only the Android manifest version code to zero.
The workflow signs this previous-version fixture and candidate with the same
ephemeral CI key. `tools/test-upgrade.py` installs the fixture, seeds Korean and
Japan as independent preferences, opens the actual update screen, taps its
install control, observes a DownloadManager transfer and confirms Android's
system installer. It then verifies installed code 1 and retained preferences.
The report distinguishes this test key from the stable local distribution key.

The `adb uninstall` operation in that script is for the disposable CI emulator
fixture setup. Normal application updates use Android's package installer and
retain the package's data.

## Distribution key

`tools/sign-apk.ps1` aligns the unsigned ARM64 APK, signs with the existing local
key, verifies its certificate and alignment, checks package identity and emits
the SHA-256 digest. No workflow receives the distribution key. Source packaging
excludes `.secrets`, keystores, caches and build outputs.
