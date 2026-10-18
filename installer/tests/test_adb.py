"""Reconexion automatica, errores de conexion y verificacion de platform-tools."""

import hashlib
import subprocess

import pytest

from tvlite import adb as adbmod
from tvlite.adb import Adb, AdbError

SAMPLE_XML = """<?xml version="1.0"?>
<ns2:repository xmlns:ns2="http://schemas.android.com/repository/android/common/02" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <remotePackage path="platforms;android-30"><archives><archive><complete><checksum type="sha1">aaaa</checksum></complete><host-os>windows</host-os></archive></archives></remotePackage>
  <remotePackage path="platform-tools">
    <revision><major>37</major></revision>
    <archives>
      <archive><complete><checksum type="sha1">477254AA5F903C15CF51001717BDF347FB6B53E0</checksum><url>x-linux.zip</url></complete><host-os>linux</host-os></archive>
      <archive><complete><checksum type="sha1">6ae73f4de6452dc57e62ec02b68eed92a4c21661</checksum><url>x-darwin.zip</url></complete><host-os>macosx</host-os></archive>
      <archive><complete><checksum type="sha1">e03e78b1d80b396f1c3358e31251cb31740e1110</checksum><url>x-win.zip</url></complete><host-os>windows</host-os></archive>
    </archives>
  </remotePackage>
</ns2:repository>"""


class ScriptedRunner:
    """Devuelve respuestas en orden y recuerda las llamadas."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        code, out, err = self.responses.pop(0) if self.responses else (0, "", "")
        return subprocess.CompletedProcess(cmd, code, out, err)


def make(runner, serial="192.168.1.50:5555", **kw):
    return Adb(serial=serial, runner=runner, sleep=lambda s: None, **kw)


def test_reconnects_and_retries_when_the_tv_dropped_the_connection():
    runner = ScriptedRunner(
        (1, "", "error: device offline"),   # 1.er intento falla
        (0, "connected to 192.168.1.50:5555", ""),  # adb connect
        (0, "ok\n", ""),                    # reintento
    )
    assert make(runner).shell("echo ok") == "ok"
    assert any(call[1:2] == ["connect"] for call in runner.calls)


def test_raises_instead_of_returning_empty_when_connection_cannot_be_recovered():
    runner = ScriptedRunner(*[(1, "", "error: device offline")] * 20)
    with pytest.raises(AdbError, match="conexion"):
        make(runner, reconnect_attempts=2).shell("pm list packages")


def test_no_reconnect_for_non_network_devices():
    runner = ScriptedRunner((1, "", "error: device offline"))
    with pytest.raises(AdbError):
        make(runner, serial="emulator-5554").shell("echo ok")
    assert not any(call[1:2] == ["connect"] for call in runner.calls)


def test_a_failing_remote_command_is_not_mistaken_for_a_lost_connection():
    runner = ScriptedRunner((1, "", "cat: /nope: No such file or directory"))
    assert make(runner).shell("cat /nope") == ""  # sin AdbError ni reconexion
    assert len(runner.calls) == 1


def test_install_multiple_builds_the_command():
    runner = ScriptedRunner((0, "Success", ""))
    make(runner).install_multiple(["a.apk", "b.apk"])
    assert runner.calls[0][-4:] == ["install-multiple", "-r", "a.apk", "b.apk"]


def test_expected_checksum_per_os():
    assert adbmod.expected_platform_tools_sha1(SAMPLE_XML, "linux") == "477254aa5f903c15cf51001717bdf347fb6b53e0"
    assert adbmod.expected_platform_tools_sha1(SAMPLE_XML, "windows") == "e03e78b1d80b396f1c3358e31251cb31740e1110"
    assert adbmod.expected_platform_tools_sha1(SAMPLE_XML, "darwin") == "6ae73f4de6452dc57e62ec02b68eed92a4c21661"
    assert adbmod.expected_platform_tools_sha1("<root/>", "linux") is None


def test_sha1_of(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hola")
    assert adbmod.sha1_of(f) == hashlib.sha1(b"hola").hexdigest()


def test_download_rejects_a_zip_whose_checksum_does_not_match(tmp_path, monkeypatch):
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return SAMPLE_XML.encode()

    def fake_retrieve(url, dest):
        dest.write_bytes(b"zip manipulado")

    monkeypatch.setattr(adbmod.urllib.request, "urlretrieve", fake_retrieve)
    monkeypatch.setattr(adbmod.urllib.request, "urlopen", lambda *a, **k: Resp())
    with pytest.raises(AdbError, match="checksum"):
        adbmod.download_adb()
    assert not (adbmod.data_dir() / "platform-tools.zip").exists()  # el archivo sospechoso se borra
