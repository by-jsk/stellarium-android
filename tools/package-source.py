#!/usr/bin/env python3
"""Create source matching the modified engine and its downloaded CMake dependencies."""
from pathlib import Path
import json
import tarfile
import hashlib

root = Path(__file__).resolve().parents[1]
version = json.loads((root/'version.json').read_text())
destination = root/'release'/f'StellarTouch-v{version["versionName"]}-source.tar.gz'
destination.parent.mkdir(exist_ok=True)
engine = root/'engine'
assert (engine/'src/mobile/MobileVersion.hpp').exists(), 'Prepare the pinned source first'
excluded = {'.git','.tools','.secrets','.ccache','__pycache__','release','stage'}

def allowed(path):
    parts = path.relative_to(root).parts
    if any(p in excluded for p in parts): return False
    if parts[0].startswith('build-'): return False
    if parts[:3] == ('engine','android','assets'):
        return path.name in {'mobile-i18n.json','COPYING','LICENSE-GPL-3.0.txt','CREDITS.md'}
    return True

with tarfile.open(destination,'w:gz',compresslevel=5) as archive:
    for path in sorted(root.rglob('*')):
        if path.is_file() and allowed(path):
            archive.add(path,arcname='StellarTouch/'+str(path.relative_to(root)),recursive=False)
    deps=root/'build-arm64-v8a/_deps'
    if deps.is_dir():
        for directory in sorted(deps.glob('*-src')):
            for path in sorted(directory.rglob('*')):
                if path.is_file() and '.git' not in path.parts:
                    archive.add(path,arcname='StellarTouch/dependency-sources/'+directory.name+'/'+str(path.relative_to(directory)),recursive=False)
print(destination)
parts=destination.parent/'source-parts'
parts.mkdir(exist_ok=True)
with destination.open('rb') as stream:
    number=0
    while True:
        data=stream.read(400*1024*1024)
        if not data: break
        part=parts/(destination.name+f'.part-{number:02d}')
        part.write_bytes(data)
        print(part.name,len(data),hashlib.sha256(data).hexdigest())
        number+=1
