#!/usr/bin/env bash
# Compila el launcher firmado con la clave de LANZAMIENTO y genera los ficheros para publicar:
#   launcher/build/litelauncher-vX.Y.Z.apk  y  launcher/build/SHA256SUMS
# Necesita LITE_KEYSTORE, LITE_KS_PASS (y opcionalmente LITE_KEY_PASS, LITE_KEY_ALIAS). Ver docs/RELEASING.md.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${LITE_KEYSTORE:?define LITE_KEYSTORE con la ruta al keystore de lanzamiento}"
bash "$HERE/build.sh"
VERSION="$(tr -d '[:space:]' < "$HERE/VERSION")"
cp "$HERE/build/litelauncher.apk" "$HERE/build/litelauncher-v$VERSION.apk"
( cd "$HERE/build" && { sha256sum "litelauncher-v$VERSION.apk" 2>/dev/null || shasum -a 256 "litelauncher-v$VERSION.apk"; } > SHA256SUMS )
cat "$HERE/build/SHA256SUMS"
