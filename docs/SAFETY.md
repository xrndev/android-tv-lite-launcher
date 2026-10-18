# Safety model and known limitations

**English** · [Español](SAFETY.es.md)

This modifies your TV's software. A mistake on an unfamiliar TV could leave it unable to boot, so:

- **Reviewed lists only.** It never removes "whatever looks like bloat". Each list states on which real devices it was verified (`verified_on`); lists without it are ignored unless you ask (`--include-unverified`) and are never preselected.
- **Protected packages** (Play Store, GMS, SystemUI, settings, providers, networking, Bluetooth, the Xiaomi launchers…) are never removed, even if a list names them. A test checks it and a list validator enforces it.
- **Reversible removal.** System apps are removed with `pm uninstall -k --user 0` and come back with `install-existing`. **User apps** lose their APK when removed (and `install-existing` then leaves a "ghost" record that *claims* to be installed), so **their APK (base + splits) is saved in the backup first** and restore reinstalls it. If the APK cannot be saved, the app is **not removed** (unless `--allow-irreversible`). Restore always verifies the package really came back.
- **Small batches with a health check.** If the TV stops responding, the batch is undone and the process stops.
- **On-disk journal.** Every action is written and synced immediately, so you can restore even if the program is interrupted or the connection drops. On a lost connection the tool stops, tells you where the backup is and leaves **Restore** available.
- **Launcher with rollback.** It installs, checks it opens, assigns it as home and verifies the Home button opens it; otherwise it restores the original and removes the new one. The original launcher is only disabled, never uninstalled.
- **Play Protect.** Some TVs show a dialog when an unknown APK is installed over ADB and the install hangs. `tvlite` turns off **only** `verifier_verify_adb_installs` while installing its own APKs, journals it and always restores it.
- **Stay-awake window.** `stay_on_while_plugged_in` is set only while the process runs, journaled and restored.
- **Verified downloads.** ADB tools against Google's published checksum, Stremio against a pinned SHA-256.
- **Dry run** (`--dry-run`) shows what it would do without changing anything.

## Known limitations

- **Installing apps from Play Store drives its UI over ADB** (it opens the app page and presses Install), which depends on Play Store's layout and on the TV being signed in to Google. It has not been tried against a real TV's Play Store with `tvlite` yet. Third-party APKs are not redistributed; Stremio is downloaded from its official site and verified.
- **Only a few apps' package names are verified** (marked `verified` in `apps.json`).
- **Debloat lists exist only for TCL** (plus generic Android/Google ones). Sony and Xiaomi lists come from public community sources and are **unverified**. There is no public list for Philips, Hisense or TD Systems. [Please contribute](../CONTRIBUTING.md).
- **GUI**: tested by an automatic test against a simulated TV and checked in screenshots, not with people using it.
- Windows is the main platform; Linux/macOS should work but are untested.
- **No release signing yet**: the launcher APK is signed with a debug key and the executables are not code-signed ([RELEASING.md](RELEASING.md)).
- Code and test comments are mostly in Spanish; the UI is bilingual (es/en).
