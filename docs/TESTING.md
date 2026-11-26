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

Capture waits for presentation after the native language checks. Android's
UIAutomator exposes Qt's OpenGL surface without its graphics-widget children,
so the close control is found either through native accessibility or from the
visible red X in the screenshot. A real ADB tap must change more than 10,000
pixels, keep the sky Activity visible, and preserve red illumination. Android
16 predictive Back is not used as a substitute for the panel's close button.
Crash checks match this app's process ID; a Google APIs emulator service crash
is retained in the log without being mislabeled as a Stellar Touch crash.

<!-- [20261126 by jsk] 새 배색과 적색 모드 전환을 확인하는 조건을 기록함. -->
The v0.1.1 native report also checks that constellation lines are enabled,
the drawing manager and persisted settings both use the high-contrast palette,
and the R button switches modes in both directions within the same activity.
The red sky screenshot must also contain visible pixels away from the menus.

The emulator's observed FPS and startup time are diagnostic measurements. They
are not performance measurements on a Galaxy S25 or all supported devices.
Hardware telescope control, every plugin configuration, external services and
physical GPS reception need additional field testing.

## Update preservation

Only the x86 CI fixture defines `STELLAR_CI_FIXTURE`. The distribution ARM64
manifest disallows cleartext HTTP and its Java flag remains a compile-time
`false`. The fixture permits a single emulator loopback server; the normal
release permits the exact public HTTPS release URL.

`tools/fixture-apk.py` sets the Android manifest version code to the preceding code.
The workflow signs this previous-version fixture and candidate with the same
ephemeral CI key. `tools/test-upgrade.py` installs the fixture, seeds Korean and
Japan as independent preferences, opens the actual update screen, taps its
install control, observes a DownloadManager transfer and confirms Android's
system installer. It then verifies the candidate version code and retained preferences.
The test waits for the installer's completed screen, closes it, and waits for
the old process to stop before relaunching the upgraded app. A PackageManager
version-code change alone does not prove the installer has finished.
The report distinguishes this test key from the stable local distribution key.

The `adb uninstall` operation in that script is for the disposable CI emulator
fixture setup. Normal application updates use Android's package installer and
retain the package's data.

## Distribution key

`tools/sign-apk.ps1` aligns the unsigned ARM64 APK, signs with the existing local
key, verifies its certificate and alignment, checks package identity and emits
the SHA-256 digest. No workflow receives the distribution key. Source packaging
excludes `.secrets`, keystores, caches and build outputs.

Run `python3 tools/prepare-release.py --evidence release/smoke --workflow-run <run-id>`
with the successful run's APK, corresponding source and both emulator reports.
