# Spec: TV dossier (optional package analysis)

**English** · [Español](device-dossier.es.md) · **Status: DRAFT for review. None of this is built.**

## 1. Goal

Let anyone using `tvlite` **optionally** share an anonymous analysis of their TV's packages **as shipped from the factory**, so the project learns what each model contains and can build **real** lists and emulator profiles (identity, `getprop`, inventory), which is exactly what cannot be found publicly.

**Not a goal:** having the program decide what can be removed from this analysis, or removing anything without a test on a real TV (see §8).

## 2. When and with what consent

- **When:** right after connecting and detecting the TV, **before applying anything**. The full factory inventory is visible, and it is useful even if the user only does a dry run.
- **Consent:** its own dialog, **separate** from the result report: "Share your TV's analysis to help others?" with **Send** / **No, thanks**. Default is **No**. A summary is shown, plus a "view the full content" button.
- **Remember my choice:** optional checkbox, unchecked by default and revocable. Without it, ask every time.
- **CLI:** `tvlite analyze <ip>` shows the analysis without sending; `--share-analysis` sends it after showing it. `--yes` does not mean consent.
- With no relay configured, nothing is offered.

## 3. What is collected (`dossier` schema v1)

**Identity and hardware:** manufacturer, brand, model, device, board, platform/SoC, Android and SDK versions, **firmware fingerprint** (`ro.build.fingerprint`), ABI, RAM, resolution and density, Play Store presence, and declared TV features (`leanback`, `live_tv`…). This yields emulator profiles with real values.

**Packages: system packages only** (`pm list packages -s`). For each one **not already in our knowledge base** these signals are sent; for known ones only the name.

| Signal | Why |
|---|---|
| package name, label, version | identification |
| updated system app? privileged? system `sharedUserId`? | how integrated it is in the firmware |
| provides a **TV input / tuner**? | almost certainly must not be touched |
| launcher (HOME)? IME? accessibility service? device admin? | basic functions |
| boot receivers, services, key permissions (network, boot, overlay) | background behaviour |
| running at idle? RAM used | real impact |
| do other system components depend on it? (best effort) | risk if removed |

**Never collected:** user-installed apps, accounts, network name or password, IP, MAC, serial number, advertising or Android ids, any persistent TV or user identifier. Strings go through the same scrubbing as the result report.

## 4. Risk hints (advisory)

The client tags each package: `core` (TV input, HOME, accessibility, IME, or integrated with dependents), `unknown` or `low-signal`. **It only helps a human reviewer.** It never enables or preselects a removal; the heuristic's version is stored. A `low-signal` hint can be wrong: `sonyshelf` looked harmless.

## 5. Transport and storage

```
tvlite --POST /v1/dossier--> relay (Cloudflare Worker) --stores--> store (D1 or R2) --short ping--> Telegram
```

- Telegram **does not store** data (about 4,000 character limit): it only gets a ping, e.g. *"New TV: Sony KD-43X80J · 214 system packages · 9 unknown · id a1b2c3"*.
- The relay validates the schema (**≤ 256 KB**, ≤ 600 packages, no free text outside bounded fields), rate-limits per IP (stored only as a hash) and stores the JSON without ever interpreting it as HTML.
- **Deduplication** without personal ids: key = hash(model + firmware fingerprint + package set).
- **Retention:** proposed 12 months. With no persistent id, **a specific submission cannot be deleted on request**, which is why only non-personal data is collected and the dialog says so.

## 6. How it is used

1. Per-model review (unknown packages ranked by how many TVs have them).
2. Research of each candidate with sources (forums, public lists, `dumpsys`).
3. **A real remove-and-restore test by a person with that TV** (existing flow: `TVLITE_EXTRA_LISTS`, `apply --only`, `restore`).
4. A list becomes "verified" with: **≥ 2 independent reports**, restore OK in all, no loss of functions after a few days, scope limited to **model or SoC** (not a whole brand). It enters as `optional`, unchecked.
5. A real emulator profile is generated from the dossier: a `models.json` entry with real `getprop` and real packages.

## 7. Planned technical changes

- `tvlite/dossier.py`: collection (`dumpsys package`, `meminfo`, `pm`), signals, heuristic, scrubbing. Fail-soft per Android version.
- Knowledge base: an index of known packages generated from the lists; lists support `match` by **model** and `firmware`.
- Relay: `/v1/dossier` route, store, short ping. The current result report does not change.
- Wizard and CLI: the dialog and commands of §2.
- `docs/TELEMETRY.md`: expanded privacy and retention.

## 8. What this does NOT solve

The analysis speeds up research; it **does not replace testing on a real TV**. No automatic signal guarantees a package is safe to remove.

## 9. Tests

- Unit tests with real `dumpsys` dumps from the emulators (API 28, 29, 30, 34) and `FakeAdb`.
- Privacy: no user app or identifier leaves in the dossier; text goes through scrubbing.
- Relay: schema, sizes, limits, deduplication, and Telegram only getting the short ping.
- Compatibility: the dossier stays valid on every tested Android version.

## 10. Decisions (made by the maintainer, delegating to technical judgment)

1. **Store: D1** (SQL), to query by model, SoC and how often each package appears.
2. **Retention: 12 months.** The dialog says so.
3. **Remember the choice:** an **optional, unchecked** checkbox, revocable. Without it, always ask.
4. **Firmware fingerprint: yes.** It identifies software, not the person; it allows grouping by version.
5. **Review:** weekly and short. The relay will send an **automatic digest** with the unknown packages most repeated across TVs, so the review takes minutes.
6. **Telegram:** a short ping per dossier while few arrive; switch to a **weekly digest** above about 10 per day (a variable, no new release needed).

## 11. Phases

1. Local collection + `tvlite analyze` (no sending). Tested on emulators and your TV.
2. Relay + store + short ping.
3. Consent dialog in the wizard and CLI.
4. Emulator-profile generator from a dossier.
