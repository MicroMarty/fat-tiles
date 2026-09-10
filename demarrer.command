#!/bin/sh
# macOS: double-click. Linux: run as a program. Keep the terminal open.
cd -P "$(dirname "$0")" || exit 1
for fat_tiles_python in python3 python; do
  if command -v "$fat_tiles_python" >/dev/null 2>&1 && "$fat_tiles_python" -c 'import sys; sys.exit(sys.version_info < (3,10))' 2>/dev/null; then
    "$fat_tiles_python" launch.py
    fat_tiles_result=$?
    if [ "$fat_tiles_result" -ne 0 ]; then
      printf '\nLe lancement a echoue. Consultez le message ci-dessus.\nAppuyez sur Entree pour fermer.'
      read -r fat_tiles_answer
    fi
    exit "$fat_tiles_result"
  fi
done
printf '\nFat Tiles a besoin de Python 3.10 ou plus recent.\nInstallez Python depuis https://www.python.org/downloads/ puis relancez ce fichier.\nSur Linux, les composants venv et pip doivent aussi etre disponibles.\nAppuyez sur Entree pour fermer.'
read -r fat_tiles_answer
exit 1
