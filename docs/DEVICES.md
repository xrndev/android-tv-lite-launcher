# Tested TVs and environments

**English** · [Español](DEVICES.es.md)

This table only lists what **has actually been tested**. Three confidence levels:

| Level | Meaning |
|---|---|
| **Real hardware** | Someone ran the tool (or the same commands) on a physical TV and checked the result. |
| **Emulated** | Passes the integration suite on an Android TV emulator. Validates the logic, not the hardware. |
| **Reported** | A user reported (with the [Device report](../.github/ISSUE_TEMPLATE/device_report.yml) form) that it works, without us having reproduced it. |

## Real hardware

| Brand / model | SoC | RAM | Android | ABI | What was tested | Result | Date |
|---|---|---|---|---|---|---|---|
| TCL Smart TV | MediaTek mt5867 | 940 MB | 11 (API 30) | armeabi-v7a | Debloat (a few dozen Google, AOSP and TCL packages; it was not recorded which were system and which user apps), Lite Launcher as home (the Google launcher had to be **disabled**: Android kept choosing it despite the HOME role), Stremio, NordVPN and Red Bull TV from Play Store, animations at 0. All applied **by hand** with the same commands `tvlite` automates. | Works. Free RAM ~250 → ~350–450 MB; the launcher uses ~40 MB versus ~130 MB. | 2026-10 |

**`tvlite` itself on this TV (2026-10-18):** `detect`, `plan`, `report`, `metrics` and `apply --dry-run` worked as expected (the plan was empty because the TV was already cleaned by hand). A **real run** removed one user app, Red Bull TV, which ships as 4 APKs (base + 3 splits): all 4 were saved to the backup, the temporary settings (stay-awake, Play Protect) were restored, and `restore` reinstalled the app from the saved APKs (5 restorations, 0 failures); it launched with no crash. This is exactly the case that broke the first time by hand.

> **Not yet exercised on real hardware with `tvlite`:** a full debloat from a stock state, the launcher switch, and app installs from Play Store. If you try it on another TV, open a Device report (`tvlite report <ip>` produces the text).

Findings from this TV that shaped the design:

- `pm uninstall -k --user 0` is only reversible for **system** apps; for user apps the APK is deleted and `install-existing` leaves a ghost record. (`tvlite` now saves a user app's APK first.)
- On this TV, assigning the HOME role **was not enough**: the Google launcher had to be disabled (`pm disable-user`).
- Most of the RAM was Google Play Services and Play Store (~260 MB), which are kept.
- The load average (~47) stays high at idle because of video-chip kernel threads in "D" state; that is normal on this TV and not a problem.
- The TV drops off the network when it goes to standby, which is why `tvlite` keeps it awake and reconnects.

## Emulated

Profiles in [`tools/emulator/profiles.json`](../tools/emulator/profiles.json). Suite: `installer/tests/integration` (detection, memory snapshot, full flow and restore with the `tcl` and `acme` fixtures, `--dry-run`, and the anonymous report).

| Profile | Android | RAM | ABI | Status |
|---|---|---|---|---|
| `atv9-1gb` | 9 (API 28) | 1 GB | x86 | 6/6 pass (2026-10-18). No-roles launcher path (`set-home-activity`). |
| `atv11-1gb` | 11 (API 30) | 1 GB | x86 | 6/6 pass (2026-10-18). |
| `atv14-2gb` | 14 (API 34) | 2 GB | x86 | 6/6 pass (2026-10-18), including Play Protect. |
| `atv11-2gb`, `atv14-4gb` | 11 / 14 | 2 / 4 GB | x86 | defined, not run (the `normal` profile is only covered by unit tests). |

Emulator findings that changed the code:

- **Play Protect (Android 14 with Play Store):** installing an unknown APK over ADB shows an on-screen dialog and the install waits forever (it did not happen on the real TCL). `tvlite` now disables **only** `verifier_verify_adb_installs` while installing its APKs, journals it and always restores the original value.
- **User apps are not restorable by `install-existing`:** the emulator reproduced the "ghost record" first seen on the TCL with Red Bull TV. Restore now reinstalls them from the APK saved in the backup, and the integration test checks the package is real afterwards.
- **Android 14 requires `targetSdk` ≥ 23** to install an APK, and ships system packages (e.g. Play Games) whose names the fixtures also use.

What the emulator does **not** cover: the real GPU and SoC, vendor-specific packages (fixtures only create empty apps with those names), nor the behavior of Play Store apps with `tvlite` (the `android-tv` images for API 28/30 do not include Play Store).

Unit tests (126, plus the emulator suites) run against a simulated TV (`installer/tests/fake_adb.py`).

## Simulated real models

There is **no emulator of real TV brands**: manufacturers do not publish their firmware, and emulators only offer generic Android TV images. What exists here are **profiles of real models** ([`tools/emulator/models.json`](../tools/emulator/models.json)): the identity, RAM and Android version of each model, plus vendor package names taken from public community lists, applied to an emulator with the matching RAM and API. They test **tvlite's logic**, not that removing those packages is safe on the physical TV. Run one with `python tools/emulator/run_models.py <id>`.

Every field of a profile states its evidence: **real** (seen on a physical TV), **public specs** (a cited datasheet) or **assumed** (not found; stated as such). The real `getprop` values of these models were **not found**: model names are commercial names.

| Model | Android / RAM | SoC | Evidence (hardware / packages) | Emulator result |
|---|---|---|---|---|
| TCL Smart TV (mt5867) | 11 / 917 MB | mt5867 | real / real | **4 of 4 passed** (2026-10-18) |
| TD Systems M32C14GLE | 11 / 1 GB | unknown | public specs / none found | **4 of 4 passed** (2026-10-18) |
| Xiaomi Mi TV 4A 32" | 9 (not confirmed) / 1 GB | Amlogic T962 | public specs / community (unverified) | **4 of 4 passed** (2026-10-18) |
| TD Systems K32DLX15GLE | 9 / 1 GB | ARM Cortex quad-core | public specs / none found | **4 of 4 passed** (2026-10-18) |
| TD Systems K32DLX10HS | 9 AOSP (no Play Store assumed) / 1.5 GB | ARM Cortex-A55 | public specs / none found | **4 of 4 passed** (2026-10-18), including that Play apps are skipped with a clear message |
| Philips 43PUS7406 | 10 / 2 GB **assumed** | unknown | Android version from specs; chipset and RAM **not found** | **4 of 4 passed** (2026-10-18; it needed three attempts because the PC ran out of memory twice) |
| Sony KD-43X80J | 10 / 2 GB **assumed** | unknown | Android version from specs; RAM **not found**; packages from community lists | **4 of 4 passed** (2026-10-18) |

Sources for each model are in `models.json`. What was **not** found: any public list of vendor packages for **Philips, Hisense and TD Systems**, so for those `tvlite` does only the generic Android and Google cleanup.

**Examples of TVs that do not work** because they are not Android: **Hisense 50A7100F** (VIDAA U3), LG (webOS), Samsung (Tizen), Roku TV. Amazon Fire TV is Android-based but unsupported (no Play Store, different launcher).

The Sony and Xiaomi lists in `tvlite` come from public community sources, are **unverified** and are never applied or preselected by default. A user reported that on a Sony TV, removing `sonyshelf` made the input sources disappear from the Home screen.

## Reported by users

_None yet._ Add yours by opening an issue with the *Device report* template and pasting the output of `tvlite report <ip>`.

## SoCs tested

| SoC | Level |
|---|---|
| MediaTek mt5867 | Real hardware |
| x86 (Android TV emulator) | Emulated |
