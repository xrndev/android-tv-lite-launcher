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

"$BT/aapt2$EXE" link --manifest "$HERE/AndroidManifest.xml" -I "$JAR" \
  --min-sdk-version 21 --target-sdk-version 30 -o "$OUT/base.apk"

javac --release 8 -g:none -Xlint:-options -cp "$JAR" -d "$OUT/classes" $(find "$HERE/src" -name '*.java')

"$BT/d8$BAT" --release --min-api 21 --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && jar uf "../unsigned.apk" classes.dex)
"$BT/zipalign$EXE" -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

KS="$HERE/debug.keystore"
[ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storepass android -keypass android \
  -alias litelauncher -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=LiteLauncher"
"$BT/apksigner$BAT" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --out "$OUT/litelauncher.apk" "$OUT/aligned.apk"
ls -l "$OUT/litelauncher.apk"
