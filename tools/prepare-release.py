#!/usr/bin/env python3
"""Produce publication files only after real runtime, upgrade and signing evidence exists."""
import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
version=json.loads((root/'version.json').read_text())
name=version['versionName']
release=root/'release'
apk=release/f'StellarTouch-v{name}.apk'
source=release/f'StellarTouch-v{name}-source.tar.gz'
assert apk.is_file() and source.is_file(),'Signed APK and matching complete source asset are required'
subprocess.run([sys.executable,str(root/'tools/check-apk.py'),str(apk),'arm64-v8a'],check=True)
required_source=['source.lock.json','version.json','mobile/MobileShell.cpp','mobile/MobileShell.hpp','mobile/i18n.json','android/src/org/byjsk/stellartouch/StellarActivity.java','tools/prepare.py','tools/build-android.sh','tools/prepare-gradle.py']
expected={'StellarTouch/'+p:hashlib.sha256((root/p).read_bytes()).digest() for p in required_source}
with tarfile.open(source,'r|gz') as archive:
    for member in archive:
        if member.name in expected:
            assert hashlib.sha256(archive.extractfile(member).read()).digest()==expected.pop(member.name),member.name
assert not expected,'Matching native source is missing from the release archive'
runtime=json.loads((args.evidence/'report.json').read_text(encoding='utf-8'))
upgrade=json.loads((args.evidence/'upgrade-report.json').read_text(encoding='utf-8'))
pages=json.loads((args.evidence.parent/'smoke-16k/report.json').read_text(encoding='utf-8'))
assert pages['passed'] and pages['android_page_size']==16384,'16-KiB runtime verification must pass'
assert runtime['passed'] and upgrade['passed'],'Execution and installer upgrade must pass'
assert runtime['versionCode']==version['versionCode']
assert upgrade['installed_versionCode']==version['versionCode']
assert upgrade['system_install_confirmed'] and upgrade['system_install_completed'] and upgrade['language_preserved']=='ko' and upgrade['region_preserved']=='JP'
assert runtime['night_non_red_fraction']<0.005 and runtime['night_visible_red_pixels']>200
signer=Path(str(apk)+'.signer.txt').read_text(encoding='utf-8-sig')
assert ('Verified using v2 scheme (APK Signature Scheme v2): true' in signer or
        'Verified using v3 scheme (APK Signature Scheme v3): true' in signer)
badging=Path(str(apk)+'.badging.txt').read_text(encoding='utf-8-sig')
assert f"name='{version['packageId']}'" in badging
assert f"versionCode='{version['versionCode']}'" in badging
base=f'https://github.com/by-jsk/app-downloads/releases/download/stellar-touch-v{name}'
notes={
    'ko':'Stellarium PC 엔진의 독립 Android 이식 시험판. 한글·6개 언어, 적색 야간 모드·밝기, 터치 검색·시간·위치, 필요할 때 플러그인 불러오기와 앱 내 업데이트.',
    'en':'Independent Android preview of the Stellarium PC engine. Six languages, red night vision and brightness, touch search/time/location, on-demand plugins and in-app updates.',
    'ja':'Stellarium PC エンジンの独立 Android 試用版。6 言語、赤色夜間表示と明るさ、タッチ検索・時刻・位置、必要時のプラグイン読み込み、アプリ内更新。',
    'zh':'Stellarium PC 引擎的独立 Android 预览版。六种语言、红色夜间模式与亮度、触控搜索/时间/位置、按需加载插件及应用内更新。',
    'es':'Vista previa independiente para Android del motor de Stellarium PC. Seis idiomas, modo nocturno rojo y brillo, búsqueda/hora/ubicación táctiles, complementos bajo demanda y actualizaciones integradas.',
    'ru':'Независимая предварительная Android-версия движка Stellarium PC. Шесть языков, красный ночной режим и яркость, сенсорные поиск/время/место, плагины по запросу и обновления в приложении.'
}
metadata={'versionCode':version['versionCode'],'versionName':name,'apk':base+'/'+apk.name,'notes':notes}
(release/'stellar-touch.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=[]
for file in (apk,source):
    digest=hashlib.file_digest(file.open('rb'),'sha256').hexdigest()
    lines.append(f'{digest}  {file.name}')
(release/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
body=f'''# 별하늘 · Stellar Touch v{name} — Android 시험판

[갤럭시 S25용 ARM64 APK 다운로드]({base}/{apk.name}) · 약 {apk.stat().st_size()/1024/1024:.0f} MiB

Stellarium PC의 실제 C++/Qt 엔진을 사용하는 독립 이식판입니다. 공식 Stellarium Mobile 제품이 아닙니다. 한국어·영어·일본어·중국어·스페인어·러시아어, 국가/언어 분리, 적색 야간 화면·밝기 조절, 터치 검색·시간·위치 및 필요할 때 불러오는 플러그인을 제공합니다.

Android 9 이상, ARM64, OpenGL ES 3.0이 필요합니다. 처음 예시 위치는 서울이므로 관측 전에 위치 또는 GPS를 설정하세요. 메인 R 버튼은 야간 모드, 설정의 현장 관측 항목은 밝기·화면 유지·성능 모드입니다.

검증: ARM64 빌드·서명·패키지·16KB ELF/ZIP 정렬 검사, Android 16 x86_64에서 실제 천체 로딩·관측지 도시 DB·시간/시간대·6개 언어/지역·설정 순서·플러그인 로드·적색 화면 검사, Android 15의 실제 16KB 페이지 에뮬레이터 실행 검사, 이전 버전 코드 0 → 1의 메타데이터 확인·다운로드·시스템 설치·설정 유지 검사. 업데이트 동작 검사는 일회용 CI 서명과 로컬 서버를 사용하며, 배포 APK는 별도 고정 배포키로 서명했습니다. Galaxy S25 실기기 성능과 모든 플러그인·망원경·온라인 서비스의 현장 검증은 완료되지 않았습니다.

Windows 전용 ASCOM/Spout·PC Oculus와 Android GLES가 지원하지 않는 ShowMySky 고급 대기는 제공하지 않습니다. 기본 대기 모델을 사용합니다. 운영체제의 권한·키보드·설치 창은 Android가 표시합니다.

GPLv3 및 데이터별 라이선스를 따릅니다. [대응 소스 전체]({base}/{source.name}), [모바일 소스와 빌드 방법](https://github.com/by-jsk/stellarium-android), [Qt 6.10.2 대응 소스](https://download.qt.io/archive/qt/6.10/6.10.2/single/), [FFmpeg n7.1.2 대응 소스](https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n7.1.2.tar.gz), [구성요소별 고지 및 빌드 출처](https://github.com/by-jsk/stellarium-android/blob/main/THIRD-PARTY.md).
'''
(release/'RELEASE.md').write_text(body,encoding='utf-8')
print('Verified release metadata, notes and SHA-256 checksums prepared')
