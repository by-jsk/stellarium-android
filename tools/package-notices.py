#!/usr/bin/env python3
"""Keep third-party binary distribution notices with the offline APK data."""
from pathlib import Path
import shutil
import sys

root=Path(__file__).resolve().parents[1]
assets=root/'engine/android/assets'
shutil.copyfile(root/'THIRD-PARTY.md',assets/'THIRD-PARTY.md')
destination=assets/'third-party-licenses'
shutil.copytree(root/'licenses',destination/'runtime',dirs_exist_ok=True)
trees=[root/'engine',root/f'build-{sys.argv[1]}/_deps']
count=0
for tree in trees:
    for file in tree.rglob('*'):
        if not file.is_file() or any(p in ('.git','assets') for p in file.relative_to(tree).parts):continue
        name=file.name.lower()
        if not (name.startswith(('license','copying','notice','copyright','authors')) or name=='credits.md'):continue
        if file.stat().st_size>1024*1024:continue
        relative=file.relative_to(tree)
        target=destination/tree.name/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(file,target);count+=1
print(f'Preserved {count} third-party license and notice files')
