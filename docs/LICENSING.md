# 배포 라이선스 점검

검토일: 2026-11-25. 확정 법률 의견이 아닌 원저작물의 공개 조건에 따른 기술적 배포 계획입니다.

- Stellarium PC와 본 모바일 수정 소스: **GPL-2.0-or-later**. 원저작자의 고지와 `LICENSE`를 유지합니다.
- 이 빌드는 Qt Charts를 포함합니다. 해당 모듈의 무료 라이선스는 **GPLv3**이므로, `or-later` 선택을 통해 **통합 APK는 GPLv3 조건으로 배포**합니다. `LICENSE-GPL-3.0.txt`를 함께 제공합니다. 소스의 기존 GPL-2.0-or-later 권리는 유지됩니다.
- Qt의 LGPL 모듈, OpenSSL, QXlsx, INDI 등 제3자 구성요소의 라이선스와 고지 역시 보존합니다. Qt와 원본 Stellarium의 이름·로고를 제휴나 공식 제품 표시로 사용하지 않습니다.
- 배포 전 원본 `CREDITS.md`, 하늘 문화의 `index.json` 내 라이선스, 글꼴·사진 고지를 APK와 대응 소스에 포함해야 합니다. 데이터 개별 조건은 GPL 설명으로 대체하지 않습니다.
- 대응 소스에는 정확한 PC 소스, 모바일 수정, 빌드 스크립트와 잠금 정보, 다운로드한 의존성의 소스 및 의존성 버전 안내를 제공합니다. 서명키·패스워드는 소스나 공개 아티팩트에 포함하지 않습니다.
- `THIRD-PARTY.md`에 Qt·FFmpeg·OpenSSL 등 변경하지 않은 플랫폼 라이브러리의 대응 소스와 빌드 지침 위치를 함께 제공합니다. 엔진·CMake 의존성의 개별 라이선스 파일은 APK의 `third-party-licenses/`에도 복사합니다.
- 별도 유료 모바일 앱의 소스·바이너리·유료 데이터는 사용하지 않습니다. 온라인 서비스는 각 서비스의 조건과 접근 권한을 따릅니다.

근거:

- [Stellarium 소스](https://github.com/Stellarium/stellarium)
- [Qt Charts 라이선스](https://doc.qt.io/qt-6.8/qtcharts-index.html#licenses)
- [Qt 6.8.3 전체 소스](https://download.qt.io/archive/qt/6.8/6.8.3/single/)
