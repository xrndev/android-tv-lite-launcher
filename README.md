# android-tv-lite-launcher

**English** · [Español](README.es.md)

Optimize a low-RAM Android TV **reversibly**: safe debloat, a tiny native launcher and the apps you pick, all from your PC over ADB.

<!-- Botón de donaciones (DESACTIVADO hasta tener el enlace de PayPal): sustituye PAYPAL_URL y quita este comentario.
[![Donate with PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?logo=paypal&logoColor=white)](PAYPAL_URL)
-->

> **Alpha.** Tested on **one real TV** (TCL, Android 11, 940 MB RAM) and on emulators. The installer has only been partly exercised on that TV. See [what is tested](#tested-so-far).

![Home screen with Lite Launcher and 9 apps](docs/img/launcher-home.png)

## Download — nothing to install

No Python or anything else needed. Download your file from [Releases](../../releases) and double-click it (macOS/Linux: `chmod +x` first):

| System | File |
|---|---|
| Windows 10/11 | `tvlite-windows-x64.exe` |
| macOS (Apple Silicon) | `tvlite-macos-arm64` |
| Linux (x86-64) | `tvlite-linux-x64` |

It detects your system and downloads, verifies and uses Google's ADB by itself. Check downloads against `SHA256SUMS`; the files are not code-signed, so Windows/macOS will ask you to confirm once.

> **No release is published yet** (it needs the maintainer's signing key, see [RELEASING](docs/RELEASING.md)). Until then: [build from source](docs/DEVELOPMENT.md).

## Which TVs work

Only TVs running **Android TV or Google TV** with Google Play Store (*Settings → About* says so). Sony, Philips, TCL, Xiaomi, TD Systems… **if** that model runs Android. **Not supported:** LG (webOS), Samsung (Tizen), Roku TV, VIDAA (e.g. Hisense 50A7100F), Fire TV. A brand name alone does not decide it.

## What it does

1. **Detects your TV** (model, Android, SoC, RAM, Play Store) and picks an optimization profile.
2. **Backs up first**: package lists, launcher, settings and the APK of every user app it removes.
3. **Debloats** only packages from reviewed lists. Play Store and the core system are protected.
4. **Installs the apps you choose** (streaming, Stremio, VPNs), automatically.
5. **Switches to [Lite Launcher](launcher/)** (16 KB, native, no animations) after checking it opens. The original launcher is only disabled.
6. **Restores everything** from the backup in one click, or by itself if something fails.

<details>
<summary>Step by step: 7 screenshots of the wizard</summary>

[Full guide](docs/GUIDE.md) · [1 Welcome](docs/img/gui-en-1-welcome.png) · [2 Connect](docs/img/gui-en-2-connect.png) · [3 Your TV](docs/img/gui-en-3-your-tv.png) · [4 Cleanup](docs/img/gui-en-4-cleanup.png) · [5 Apps](docs/img/gui-en-5-apps.png) · [6 Summary](docs/img/gui-en-6-summary.png) · [7 Result](docs/img/gui-en-7-result.png)

<img src="docs/img/gui-en-4-cleanup.png" width="48%"> <img src="docs/img/gui-en-5-apps.png" width="48%">
<img src="docs/img/gui-en-3-your-tv.png" width="48%"> <img src="docs/img/gui-en-7-result.png" width="48%">

</details>

## Safety in one minute

Reviewed lists only (never "whatever looks like bloat"), protected packages, a backup before any change, small batches with a health check, and automatic rollback. Everything is reversible; user apps are saved as APK first. Details and known limitations: [docs/SAFETY.md](docs/SAFETY.md).

## Tested so far

| Environment | Type | What was tested |
|---|---|---|
| TCL Smart TV (mt5867, 940 MB, Android 11) | **Real hardware** | Lists, launcher and apps by hand; `tvlite`: read-only commands, dry run and a real remove + restore of a 4-APK app |
| Emulators: Android 9, 11, 14 (1–2 GB) | Emulated | Full flow: debloat, launcher switch, restore |
| Profiles of real models: TCL, TD Systems ×3, Xiaomi, Philips, Sony | Simulated | The logic, with each model's identity, RAM and packages: 4 of 4 tests each |

An emulator is not a real TV: it validates the logic, not the hardware or that removing a brand's packages is safe. Per-model detail, evidence level and sources: [docs/DEVICES.md](docs/DEVICES.md).

## Privacy

`tvlite` sends **nothing** by itself. At the end it can offer an **anonymous result report** (TV model, Android, SoC, RAM, what worked and the error, with IPs, user names and serial numbers removed). You see the exact content first and only **Send** sends it. [Details](docs/TELEMETRY.md).

## Contribute

The most useful help is **reporting your TV**: `tvlite report <ip>` and paste the result in an issue. Other brands need package lists. [CONTRIBUTING](CONTRIBUTING.md) · [Development](docs/DEVELOPMENT.md) · [Apache-2.0](LICENSE)
