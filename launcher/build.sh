#!/usr/bin/env bash
# Compila el launcher sin Gradle: aapt2 + javac + d8 + zipalign + apksigner.
# Necesita: JDK 17+ (JAVA_HOME o en el PATH) y el SDK de Android con build-tools >= 35 y la plataforma android-30.
#   SDK: ANDROID_SDK_ROOT, o tools/android-sdk dentro del repo.
# (build-tools 34 trae un d8 que falla con los .class de JDK 21; con 35 compila bien.)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$ROOT/tools/android-sdk}}"
[ -d "$SDK/build-tools" ] || { echo "No encuentro el SDK de Android en $SDK (define ANDROID_SDK_ROOT)" >&2; exit 1; }
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
JAR="$(ls "$SDK"/platforms/android-*/android.jar | sort -V | tail -1)"
[ -n "${JAVA_HOME:-}" ] && export PATH="$JAVA_HOME/bin:$PATH"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) EXE=".exe"; BAT=".bat" ;;
  *) EXE=""; BAT="" ;;
esac

OUT="$HERE/build"
rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex"

# Version de launcher/VERSION (X.Y.Z); versionCode = X*10000 + Y*100 + Z
VERSION="$(tr -d '[:space:]' < "$HERE/VERSION")"
IFS=. read -r V_MAJOR V_MINOR V_PATCH <<< "$VERSION"
VERSION_CODE=$((V_MAJOR * 10000 + V_MINOR * 100 + V_PATCH))

"$BT/aapt2$EXE" link --manifest "$HERE/AndroidManifest.xml" -I "$JAR" \
  --min-sdk-version 21 --target-sdk-version 30 \
  --version-code "$VERSION_CODE" --version-name "$VERSION" -o "$OUT/base.apk"

javac --release 8 -g:none -Xlint:-options -cp "$JAR" -d "$OUT/classes" $(find "$HERE/src" -name '*.java')

"$BT/d8$BAT" --release --min-api 21 --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && jar uf "../unsigned.apk" classes.dex)
"$BT/zipalign$EXE" -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

# Firma: de lanzamiento si LITE_KEYSTORE esta definido (ver docs/RELEASING.md); si no, clave de depuracion local.
if [ -n "${LITE_KEYSTORE:-}" ]; then
  KS="$LITE_KEYSTORE"; KS_PASS="${LITE_KS_PASS:?define LITE_KS_PASS}"; KEY_PASS="${LITE_KEY_PASS:-$KS_PASS}"; ALIAS="${LITE_KEY_ALIAS:-litelauncher}"
  [ -f "$KS" ] || { echo "No existe el keystore $KS" >&2; exit 1; }
else
  KS="$HERE/debug.keystore"; KS_PASS=android; KEY_PASS=android; ALIAS=litelauncher
  [ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storepass android -keypass android \
    -alias litelauncher -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=LiteLauncher"
fi
"$BT/apksigner$BAT" sign --ks "$KS" --ks-key-alias "$ALIAS" --ks-pass "pass:$KS_PASS" --key-pass "pass:$KEY_PASS" \
  --out "$OUT/litelauncher.apk" "$OUT/aligned.apk"
ls -l "$OUT/litelauncher.apk"
