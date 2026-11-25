# 별하늘 · Stellar Touch

Stellarium PC의 실제 C++/Qt 엔진을 Android에 이식하는 독립 GPL 프로젝트입니다. 공식 Stellarium Mobile 제품이 아니며 Stellarium 개발팀의 보증이나 제휴를 주장하지 않습니다.

**개발 중 — 빌드·실행·업데이트 검증이 끝나기 전에는 설치용 릴리스로 표시하지 않습니다.**

## 구조와 빌드

`source.lock.json`에 고정한 공식 PC 소스를 `engine/`으로 받은 다음 `tools/prepare.py`로 이 저장소의 모바일 계층을 적용합니다. PC 엔진을 웹사이트나 원격 PC 연결로 대체하지 않습니다.

```sh
git clone https://github.com/by-jsk/stellarium-android.git
cd stellarium-android
python3 tools/prepare.py --fetch
QT_ROOT_DIR=/path/to/Qt/6.8.3/android_arm64_v8a \
QT_HOST_PATH=/path/to/Qt/6.8.3/gcc_64 \
ANDROID_SDK_ROOT=/path/to/android-sdk \
ANDROID_NDK_ROOT=/path/to/android-sdk/ndk/26.1.10909125 \
bash tools/build-android.sh
```

GitHub Actions가 ARM64 설치용 APK와 x86_64 에뮬레이터 검증용 APK를 각각 빌드합니다. 서명키를 저장소에 넣지 않습니다. 빌드 산출물은 테스트 결과와 함께 검토한 후 동일한 배포키로 서명합니다.

## 라이선스와 배포

Stellarium 소스는 GPL-2.0-or-later입니다. 이 빌드에 포함되는 Qt Charts의 GPLv3 조건에 맞춰 통합 APK는 GPLv3으로 배포합니다. GPL 조건(저작권·라이선스 유지, 변경 고지, APK에 대응하는 전체 소스 및 빌드 방법 제공)을 준수하면 수정과 배포가 허용됩니다. 단순히 PC판이 무료라는 이유로 모든 자산·상표·온라인 서비스를 자유롭게 재사용할 수 있는 것은 아닙니다. 하늘 문화·그림·사진·글꼴의 개별 조건도 유지합니다. 상용 모바일 앱의 바이너리나 유료 데이터를 복사하지 않습니다. 자세한 내용은 `docs/LICENSING.md`를 확인하세요.

- [공식 PC 소스와 라이선스](https://github.com/Stellarium/stellarium)
- [공식 Android 빌드 지침](https://github.com/Stellarium/stellarium/blob/master/BUILDING.md#for-android-not-officially-supported-developers-only)
- [GPL v2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)

이는 위 공개 라이선스에 대한 일반적 설명이며, 특정 국가의 모든 법률 문제에 대한 확정적 법률 의견은 아닙니다.

## 지원 범위

PC의 기본 엔진, 기본 카탈로그, 하늘 문화, 시간·위치, 스크립트와 기본 활성 플러그인을 유지하는 것이 목표입니다. `docs/FEATURES.md`에서 실제 빌드·실행 검증 여부를 구분합니다. 플랫폼 전용 기능을 검증 없이 지원한다고 표시하지 않습니다.

한국어, 영어, 일본어, 중국어, 스페인어, 러시아어를 제공합니다. 국가/지역과 언어는 별도로 저장하며 기기 기본값으로 복원할 수 있습니다. 설정에는 사용법, 설명, 언어 설정, 업데이트 순서로 항목을 둡니다.
