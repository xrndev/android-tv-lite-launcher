"""Los APK descargados (Stremio) se verifican contra un SHA-256 fijado antes de instalarse."""

import datetime
import hashlib

from fake_adb import FakeAdb
from tvlite import appinstall
from tvlite.journal import Journal

CONTENT = b"apk de prueba"
APP = {
    "id": "demo", "name": "Demo", "package": "demo.app", "method": "apk", "version": "1.0", "checked": "2026-10-18",
    "apk": {"armeabi-v7a": "https://example.invalid/demo.apk"},
    "sha256": {"armeabi-v7a": hashlib.sha256(CONTENT).hexdigest()},
}


def downloader(content):
    def fetch(url, dest):
        dest.write_bytes(content)
    return fetch


def test_matching_sha256_installs(tmp_path):
    adb = FakeAdb()
    result = appinstall.install_apk(adb, APP, ["armeabi-v7a"], Journal(tmp_path / "j"), lambda m: None, downloader(CONTENT))
    assert result.ok and any("install installed.demo" in line for line in adb.log)


def test_tampered_download_is_rejected_and_not_installed(tmp_path):
    adb = FakeAdb()
    result = appinstall.install_apk(adb, APP, ["armeabi-v7a"], Journal(tmp_path / "j"), lambda m: None, downloader(b"manipulado"))
    assert not result.ok and "SHA-256" in result.detail
    assert not any(line.startswith("install ") for line in adb.log)  # no llego a instalarse
    assert not (appinstall.data_dir() / "downloads" / "demo.apk").exists()  # y el fichero sospechoso se borra


def test_apps_without_a_pinned_hash_still_install(tmp_path):
    app = {**APP}
    app.pop("sha256")
    result = appinstall.install_apk(FakeAdb(), app, ["armeabi-v7a"], Journal(tmp_path / "j"), lambda m: None, downloader(b"x"))
    assert result.ok


def test_real_catalog_pins_a_hash_for_every_stremio_variant():
    stremio = next(a for a in appinstall.load_apps()["apps"] if a["id"] == "stremio")
    assert set(stremio["sha256"]) == set(stremio["apk"])
    assert all(len(h) == 64 for h in stremio["sha256"].values())


def test_stale_warning_only_after_a_year():
    today = datetime.date(2026, 10, 18)
    assert appinstall.stale_warning(APP, today) == ""
    old = datetime.date(2028, 1, 1)
    assert "Demo 1.0" in appinstall.stale_warning(APP, old) and "dias" in appinstall.stale_warning(APP, old)
    assert appinstall.stale_warning({"name": "X", "checked": "2000-01-01"}, today) == ""  # sin hash fijado no aplica
