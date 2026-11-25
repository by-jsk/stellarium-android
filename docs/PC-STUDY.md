# Stellarium PC 소스 스터디와 Android 이식 방향

대상 소스는 `source.lock.json`의 커밋으로 고정했습니다. 버전이 바뀌면 `tools/prepare.py`가 원본 문맥 변경을 확인하고 실패하도록 해, 패치를 잘못 적용한 채 배포하지 않습니다.

## 확인한 구조

- `src/main.cpp`: Qt 앱 생성, 사용자 설정과 데이터 경로, 엔진 실행 준비. 기존 개발자용 Android 경로는 공유 저장소에 데이터를 따로 복사하고 전체 파일 접근을 허용하는 방식입니다. 이 앱은 데이터를 APK에 포함하고 설정을 앱 전용 경로에 보관하도록 바꿉니다.
- `src/StelMainView.cpp`: OpenGL/GLES 렌더링, 핀치 제스처, 프레임 제어, 야간 효과. 기존 야간 효과의 녹색 성분을 제거하고 적색 밝기를 조절합니다. 기본 프레임 상한을 60으로 제한하고 정지 상태의 렌더링 빈도를 낮춥니다.
- `src/core/StelCore.*`: 시간, 좌표 변환, 관측자 위치. 자체 간이 계산으로 교체하지 않고 PC 구현을 사용합니다.
- `src/core/modules/`: 별 카탈로그, 태양계와 천체력, 심원천체, 별자리, 대기, 지형과 은하수. 기본 데이터는 CMake 설치 목록으로 모아 APK에 포함합니다. 선택적 추가 카탈로그의 다운로드 기능은 원래 엔진에 남깁니다.
- `StelActionMgr`: PC의 키보드·도구 모음 동작을 공통 액션으로 등록합니다. 모바일 도구 목록은 이 등록 목록에서 생성하므로 개별 기능의 별도 흉내 코드를 만들지 않습니다.
- `src/gui/StelDialog.cpp`: 상세 설정과 플러그인 패널. 기존 동작은 유지하고 작은 화면에서 스크롤할 수 있도록 감쌉니다.
- `po/`: 인터페이스, 천체 이름, 하늘 문화와 스크립트 설명의 번역. PC 번역과 모바일 계층의 6개 언어 문구를 함께 사용합니다.

## 현재 소스에서 기본 빌드하는 29개 플러그인

AngleMeasure, ArchaeoLines, Calendars, EquationOfTime, Exoplanets, LensDistortionEstimator, MeteorShowers, MosaicCamera, NavStars, NebulaTextures, Novae, ObjectVisibility, Observability, Oculars, OnlineQueries, Planes, PointerCoordinates, Pulsars, Quasars, RemoteControl, RemoteSync, Satellites, Scenery3d, SkyCultureMaker, SolarSystemEditor, Supernovae, TelescopeControl, TextUserInterface, TimeNavigator.

빌드에 포함되는 것과 시작할 때 로드되는 것은 다릅니다. 큰 초기 데이터 처리가 필요한 Satellites와 SolarSystemEditor는 자동 로드를 기본으로 끄며, **도구 → 플러그인**에서 필요할 때 바로 불러와 설정을 엽니다. 모든 기본 플러그인의 설치 소스는 유지합니다. 빌드 성공만으로 실제 망원경·외부 서버·모든 플러그인의 현장 동작 검증을 대신하지 않습니다.

## Android에서 그대로 제공할 수 없는 항목

원본 CMake가 Android에서 제외하는 ShowMySky 고급 대기(데스크톱 OpenGL 3.3 필요), Windows 전용 Spout와 ASCOM, PC Oculus 장치 연동은 Android의 동일 기능으로 표시하지 않습니다. 기본 대기 모델과 Android에서 빌드되는 나머지 기능을 사용합니다.

## 검증 단계

1. 고정 소스의 패치 적용과 재적용, 6개 언어 문구·사용법·패키지·권한의 정적 검사.
2. ARM64와 x86_64에서 실제 컴파일 및 비어 있지 않은 APK 산출물 확인.
3. Android 에뮬레이터에서 천체 로딩, 시간 변경, 엔진 액션, 언어·지역 저장, 설정 순서와 실제 적색 화면 검사.
4. 배포키로 서명 후 패키지 ID·버전·인증서·정렬 검사. 이전 버전과의 업데이트·데이터 유지 검사 결과를 기록한 후 공개 다운로드 정보를 갱신.

설치 대상은 갤럭시 S25이며, 에뮬레이터 결과와 S25 실기기 결과를 구분해 기록합니다.
