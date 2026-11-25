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
parser.add_argument('--workflow-run', type=int, required=True,
                    help='GitHub Actions run ID that produced the supplied build and test evidence')
args=parser.parse_args()
if args.workflow_run <= 0:
    parser.error('--workflow-run must be a positive numeric GitHub Actions run ID')
workflow_url=f'https://github.com/by-jsk/stellarium-android/actions/runs/{args.workflow_run}'
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
# [20261126 by jsk] 두 에뮬레이터에서 후보 버전과 별자리 선 표시, 배색, 적색 전환을 대조함.
for report in (runtime, pages):
    assert report['versionCode']==version['versionCode'],'Runtime evidence must match the release version'
    assert report['constellation_lines_visible_by_default'] is True,'Constellation lines must be enabled'
    assert report['constellation_line_palette_applied'] is True,'Constellation line palette must be applied'
    assert report['night_button_round_trip'] is True,'The night button must switch on and off safely'
    assert report['night_non_red_fraction']<0.005 and report['night_visible_red_pixels']>200
previous_code=upgrade['previous_versionCode']
installed_code=upgrade['installed_versionCode']
assert type(previous_code) is int and previous_code==version['versionCode']-1
assert type(installed_code) is int and installed_code==version['versionCode']
assert upgrade['system_install_confirmed'] and upgrade['system_install_completed'] and upgrade['language_preserved']=='ko' and upgrade['region_preserved']=='JP'
signer=Path(str(apk)+'.signer.txt').read_text(encoding='utf-8-sig')
assert ('Verified using v2 scheme (APK Signature Scheme v2): true' in signer or
        'Verified using v3 scheme (APK Signature Scheme v3): true' in signer)
badging=Path(str(apk)+'.badging.txt').read_text(encoding='utf-8-sig')
assert f"name='{version['packageId']}'" in badging
assert f"versionCode='{version['versionCode']}'" in badging
base=f'https://github.com/by-jsk/app-downloads/releases/download/stellar-touch-v{name}'
notes={
    'ko':'적색 모드 전환 중 앱이 종료되는 문제를 수정하고 별자리 선을 밝은 하늘색으로 바꿨습니다. 메뉴 숨기기와 복원, 성도 글자 크기 조절, 천체 설명 닫기를 추가했습니다.',
    'en':'Fixed a crash when switching red night mode and made constellation lines bright sky blue. Added controls to hide and restore menus, resize chart text, and close object details.',
    'ja':'赤色の夜間モードを切り替えるとアプリが終了する不具合を修正し、星座線を明るい空色にしました。メニューの表示切替、星図の文字サイズ調整、天体情報を閉じる操作を追加しました。',
    'zh':'修复了切换红色夜间模式时的闪退，将星座连线改为明亮的天蓝色。新增隐藏和恢复菜单、调整星图文字大小以及关闭天体信息的功能。',
    'es':'Se corrigió un cierre al cambiar el modo nocturno rojo y se aclararon a azul celeste las líneas de las constelaciones. Ahora puedes ocultar y mostrar los menús, ajustar el tamaño del texto de la carta celeste y cerrar la ficha del objeto.',
    'ru':'Исправлено аварийное завершение при переключении красного ночного режима, линии созвездий стали ярко-голубыми. Теперь можно скрывать и возвращать меню, менять размер текста на карте неба и закрывать сведения об объекте.'
}
metadata={'versionCode':version['versionCode'],'versionName':name,'apk':base+'/'+apk.name,'notes':notes}
(release/'stellar-touch.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=[]
for file in (apk,source):
    digest=hashlib.file_digest(file.open('rb'),'sha256').hexdigest()
    lines.append(f'{digest}  {file.name}')
(release/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
body=f'''# 별하늘 · Stellar Touch v{name} — Android 시험판

[갤럭시 S25용 ARM64 APK 다운로드]({base}/{apk.name}) · 약 {apk.stat().st_size/1024/1024:.0f} MiB

Stellarium PC의 실제 C++/Qt 엔진을 사용하는 독립 이식판입니다. 공식 Stellarium Mobile 제품이 아닙니다. 한국어·영어·일본어·중국어·스페인어·러시아어, 국가/언어 분리, 적색 야간 화면·밝기 조절, 터치 검색·시간·위치 및 필요할 때 불러오는 플러그인을 제공합니다.

Android 9 이상, ARM64, OpenGL ES 3.0이 필요합니다. 처음 예시 위치는 서울이므로 관측 전에 위치 또는 GPS를 설정하세요. 메인 R 버튼은 야간 모드, 설정의 현장 관측 항목은 밝기·화면 유지·성능 모드입니다. 패널은 오른쪽 위 × 버튼으로 닫습니다.

## 이번 버전 변경 사항

{notes['ko']}

## 검증

- ARM64 APK의 패키지·서명·16KB ELF/ZIP 정렬을 확인했습니다.
- Android 16과 실제 16KB 페이지 Android 15 에뮬레이터에서 천체 로딩, 별자리 선 기본 표시·배색, R 버튼 왕복 전환, 적색 화면을 확인했습니다.
- 에뮬레이터에서 버전 코드 {previous_code} → {installed_code} 업데이트를 실행하고 시스템 설치 완료와 기존 언어·지역 설정 유지를 확인했습니다. 설치 시험은 일회용 CI 서명과 로컬 서버를 사용했고, 배포 APK는 고정 배포키로 서명했습니다.
- Galaxy S25 실기기 성능과 플러그인·망원경·온라인 서비스의 현장 동작은 별도 확인이 필요합니다.

Windows 전용 ASCOM/Spout·PC Oculus와 Android GLES가 지원하지 않는 ShowMySky 고급 대기는 제공하지 않습니다. 기본 대기 모델을 사용합니다. 운영체제의 권한·키보드·설치 창은 Android가 표시합니다.

[실행·업데이트 시험 보고서와 화면]({base}/verification-v{name}.zip) · [GitHub Actions 검증 실행]({workflow_url})

GPLv3 및 데이터별 라이선스를 따릅니다. [대응 소스 전체]({base}/{source.name}), [모바일 소스와 빌드 방법](https://github.com/by-jsk/stellarium-android), [Qt 6.10.2 대응 소스](https://download.qt.io/archive/qt/6.10/6.10.2/single/), [FFmpeg n7.1.2 대응 소스](https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n7.1.2.tar.gz), [구성요소별 고지 및 빌드 출처](https://github.com/by-jsk/stellarium-android/blob/main/THIRD-PARTY.md).
'''
(release/'RELEASE.md').write_text(body,encoding='utf-8')
print('Verified release metadata, notes and SHA-256 checksums prepared')
