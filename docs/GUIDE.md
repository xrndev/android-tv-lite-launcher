# Step-by-step guide

**English** · [Español](GUIDE.es.md)

## Before you start

Enable developer options on the TV: *Settings → Device Preferences → About → press "Build" 7 times*, then enable USB debugging and **network debugging** (on Android 11+ it may be called *Wireless debugging* and ask for a pairing code). The PC and the TV must be on the same network; note the TV's IP (*Settings → Network*). The wizard explains all of this on its first screen.

> **When you are done, turn network debugging off again.** While it is on, any device on your network can connect to the TV.

## The wizard

Screenshots of `tvlite` walking through a **simulated TV** (the same one the tests use); on a real TV the data is your TV's. Regenerate them with `python tools/docs/capture_gui.py docs/img en`.

**1. Before you start** — how to enable developer options and network debugging.

![Step 1](img/gui-en-1-welcome.png)

**2. Connect** — type the TV's IP (or the pairing address and code on Android 11+ *Wireless debugging*). The TV may ask you to accept this PC's key. ADB downloads and verifies itself.

![Step 2](img/gui-en-2-connect.png)

**3. Your TV** — brand, model, Android, SoC, RAM, storage, whether it has Play Store, and the optimization profile. A button copies an anonymous report for GitHub issues.

![Step 3](img/gui-en-3-your-tv.png)

**4. Cleanup** — only packages from reviewed lists, preselected by RAM. Items with `(!)` may remove a feature; user apps are tagged because their APK is saved before removal.

![Step 4](img/gui-en-4-cleanup.png)

**5. Apps to install** — streaming, players, Stremio and VPNs. Most come from **Play Store** (the TV must be signed in to Google); Stremio is downloaded from its official site and verified.

![Step 5](img/gui-en-5-apps.png)

**6. Summary** — what is about to happen. Tick *Dry run only* to see the plan without changing anything.

![Step 6](img/gui-en-6-summary.png)

**7. Result** — backup saved first, changes applied, before/after RAM, the reminder to turn network debugging off, and a **Restore the TV** button.

![Step 7](img/gui-en-7-result.png)

**8. On the TV** — an example of the final home screen with 9 apps (a real TV): full-bleed banners with rounded corners, a clock and Play Store always first. A long press on any app moves it, hides it or shows its info.

![Final home](img/launcher-home.png)

## Command line

```bash
tvlite plan 192.168.1.50                 # what would be removed, touching nothing
tvlite apply 192.168.1.50 --dry-run
tvlite apply 192.168.1.50 --apps stremio,nordvpn
tvlite metrics 192.168.1.50              # available RAM and packages right now
tvlite report 192.168.1.50               # anonymous report to paste in an issue (nothing is sent)
tvlite backups                           # saved backups
tvlite restore 192.168.1.50 <backup-folder>
```
