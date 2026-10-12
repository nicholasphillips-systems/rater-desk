#!/bin/bash
# Build "dist/Rater Desk.exe" from Linux, using Windows Python under Wine.
#
# The first run downloads Windows Python, PyQt6 and PyInstaller (~110 MB) into
# ~/.cache/rater-desk-winbuild; later runs reuse them. It has its own Wine
# prefix, so no other Wine setup on this machine is touched.
set -euo pipefail
cd "$(dirname "$0")"

PY_VERSION=3.12.10
CACHE="${RATER_DESK_WINBUILD:-$HOME/.cache/rater-desk-winbuild}"
export WINEPREFIX="$CACHE/prefix"
export WINEARCH=win64
export WINEDEBUG=-all
# Never let Wine pop up its Mono/Gecko installers or register file associations.
export WINEDLLOVERRIDES="mscoree,mshtml=;winemenubuilder.exe=d"

PYTHON="$CACHE/python/tools/python.exe"

if [ ! -f "$PYTHON" ]; then
  mkdir -p "$CACHE/python"
  echo "Downloading Windows Python $PY_VERSION..."
  curl -fL --retry 3 -o "$CACHE/python.nupkg" \
    "https://api.nuget.org/v3-flatcontainer/python/$PY_VERSION/python.$PY_VERSION.nupkg"
  unzip -q -o "$CACHE/python.nupkg" -d "$CACHE/python"
  rm "$CACHE/python.nupkg"
fi

if [ ! -d "$WINEPREFIX" ]; then
  echo "Creating the Wine prefix..."
  wineboot --init
  wineserver --wait
fi

echo "Installing PyQt6 and PyInstaller..."
wine "$PYTHON" -m pip install --quiet --disable-pip-version-check \
  --no-warn-script-location -r requirements.txt pyinstaller

echo "Building..."
wine "$PYTHON" -m PyInstaller --noconfirm --clean \
  --distpath dist --workpath "$CACHE/work" rater-desk.spec
wineserver --wait

ls -lh "dist/Rater Desk.exe"
