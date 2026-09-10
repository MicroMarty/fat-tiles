"""Build a native executable on the current OS and clean, shareable source archives."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parent
RELEASE=ROOT/'release'
SOURCE_FILES=['launch.py','server.py','terrain.py','runtime_paths.py','requirements.txt','README.md','VALIDATION.md','PARTAGER.md','ATTRIBUTION.txt','Dockerfile','.dockerignore','demarrer.cmd','demarrer.command','demarrer-linux.sh','build_release.py']


def source_archives():
    paths=[ROOT/name for name in SOURCE_FILES]+sorted((ROOT/'static').rglob('*'))+sorted((ROOT/'tests').glob('*.py'))+sorted((ROOT/'tests').glob('*.cjs'))
    paths=[p for p in paths if p.is_file()]
    with zipfile.ZipFile(RELEASE/'Fat-Tiles-Multiplateforme.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            name='Fat-Tiles/'+path.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(name)
            info.create_system=3
            info.external_attr=(0o100755 if path.suffix in ('.command','.sh') else 0o100644)<<16
            archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
    with tarfile.open(RELEASE/'Fat-Tiles-Multiplateforme.tar.gz','w:gz') as archive:
        for path in paths:
            info=archive.gettarinfo(str(path),arcname='Fat-Tiles/'+path.relative_to(ROOT).as_posix())
            info.mode=0o755 if path.suffix in ('.command','.sh') else 0o644
            with path.open('rb') as stream:archive.addfile(info,stream)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-only',action='store_true')
    parser.add_argument('--onedir',action='store_true',help='Optional diagnostic build')
    args=parser.parse_args()
    RELEASE.mkdir(exist_ok=True)
    if not args.source_only:
        command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir' if args.onedir else '--onefile','--console','--name','Fat-Tiles','--add-data',f'{ROOT / "static"}{os.pathsep}static','--add-data',f'{ROOT / "ATTRIBUTION.txt"}{os.pathsep}.',str(ROOT/'launch.py')]
        subprocess.check_call(command,cwd=ROOT)
        if args.onedir:
            return
        suffix='.exe' if os.name=='nt' else ''
        executable=ROOT/'dist'/f'Fat-Tiles{suffix}'
        target=RELEASE/executable.name
        shutil.copy2(executable,target)
        licenses=RELEASE/'Licences-dependances.txt'
        with licenses.open('w',encoding='utf-8') as stream:
            stream.write('Fat Tiles — dépendances incorporées au programme autonome.\n\n')
            for name in ('numpy','Pillow','pyinstaller'):
                distribution=importlib.metadata.distribution(name)
                stream.write(f'\n=== {name} {distribution.version} ===\n')
                for file in distribution.files or []:
                    if any(word in str(file).lower() for word in ('license','copying')) and str(file).endswith(('.txt','.md','LICENSE','COPYING')):
                        path=distribution.locate_file(file)
                        if path.is_file():stream.write(path.read_text(encoding='utf-8',errors='replace')+'\n')
            for file in (ROOT/'static'/'vendor').glob('*LICENSE*'):stream.write(file.read_text(encoding='utf-8')+'\n')
            python_license=Path(sys.base_prefix)/'LICENSE.txt'
            if python_license.exists():stream.write(python_license.read_text(encoding='utf-8')+'\n')
        system={'Windows':'Windows','Darwin':'macOS','Linux':'Linux'}.get(platform.system(),platform.system())
        arch='x64' if platform.machine().lower() in ('amd64','x86_64') else platform.machine()
        with zipfile.ZipFile(RELEASE/f'Fat-Tiles-{system}-{arch}.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for path in (target,ROOT/'PARTAGER.md',ROOT/'ATTRIBUTION.txt',licenses):archive.write(path,'Fat-Tiles/'+path.name)
        (RELEASE/'build-info.json').write_text(json.dumps(dict(system=platform.platform(),python=sys.version,packages={name:importlib.metadata.version(name) for name in ('numpy','Pillow','pyinstaller')}),indent=2),encoding='utf-8')
    source_archives()
    checksums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in RELEASE.iterdir() if p.suffix in ('.zip','.gz','.exe')}
    (RELEASE/'SHA256.json').write_text(json.dumps(checksums,indent=2),encoding='utf-8')
    print('Archives prêtes dans',RELEASE)


if __name__=='__main__':main()
