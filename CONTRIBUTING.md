# Contributing

**English** · [Español](CONTRIBUTING.es.md)

Thanks for wanting to help. This project touches other people's TVs, so **safety and honesty about what is tested come before quantity**.

## The most useful thing: report your TV

1. Enable developer options and network debugging on the TV (see the README).
2. Run, **without changing anything**:
   ```bash
   tvlite report <your-tv-ip>
   ```
   It prints an anonymous report (model, Android, SoC, RAM, which packages `tvlite` would remove, and the vendor system packages that no list covers yet). **Nothing is sent**: read it, then paste it into a **Device report** issue. It contains no serial number, IP, accounts or user-installed apps.
3. Optionally try the real thing and tell us how it went:
   ```bash
   tvlite apply <ip> --dry-run      # shows the plan
   tvlite apply <ip>                # applies it (backs everything up first)
   tvlite restore <ip> <backup>     # did it bring the original state back?
   ```
   Did it boot fine? Does Home open the new launcher? Did restore bring every package back?

That goes into [docs/DEVICES.md](docs/DEVICES.md) as *reported*.

## Adding a package list (another brand or SoC)

Lists live in [`installer/tvlite/data/packages.json`](installer/tvlite/data/packages.json) and, for contributions, in `installer/tvlite/data/community/*.json` (same format, just the `lists` key).

Rules, all enforced by `validate_catalog` and the tests:

- **`verified_on` is required** and must name **real** devices ("Brand Model, SoC, Android X"). Without it the list is ignored by default. If you have not tried it on a physical TV, do not set `verified_on`: set `notes` explaining where each package comes from.
- **Never** protected packages (Play Store, GMS, SystemUI, settings, providers, networking, Bluetooth, launchers…). The validator fails if one appears.
- **`tier`** honestly: `safe` (nobody will notice), `recommended` (dispensable on a low-RAM TV), `aggressive` (may remove a feature, so add `breaks` explaining it), `optional` (never preselected: voice, accessibility…).
- **`match`** as narrow as possible (`manufacturer`, `brand`, `model`, `soc`).
- System apps are removed and restored with `install-existing`. If a package is a *user* app on your TV, `tvlite` saves its APK first so it can be restored; say so in the PR.
- Test the list **before** proposing it, including restore:
  ```bash
  TVLITE_EXTRA_LISTS=my_list.json tvlite plan <ip>
  TVLITE_EXTRA_LISTS=my_list.json tvlite apply <ip> --only package.one,package.two
  tvlite restore <ip> <backup-folder>
  ```
- State the result of `tvlite restore` in the PR: did every package come back?

## Code

```bash
cd installer
pip install -e ".[dev]"
python -m pytest                       # unit tests, with FakeAdb (no hardware)
```

- Every interaction with Android goes through `tvlite/android.py` and is simulated in `tests/fake_adb.py`. If you add a command, teach it to `FakeAdb`.
- Test the **failures**, not just the happy path (broken launcher, TV that stops answering, lost connection, app that does not restore).
- If you change something safety-related (protected packages, reversibility, restore), check that your change **makes a test fail when you remove it** (a manual mutation check is enough).
- The GUI is a thin layer: logic goes in the core, where it can be tested without a screen. In Tkinter, **never touch Tk variables from threads**.
- Emulator tests: see the README → *Android TV emulators*. Add a row to `docs/DEVICES.md` only after you have actually run the profile.
- Comments in the code are mostly Spanish; English is welcome for new code.

## Honesty about what is tested

Do not mark a device as *tested* if you only saw it in an emulator, or an app as `verified` if you have not seen its package on a real TV. The table in [docs/DEVICES.md](docs/DEVICES.md) separates **real hardware**, **emulated** and **reported** on purpose.

## License

By contributing you agree your contribution is published under [Apache-2.0](LICENSE).
