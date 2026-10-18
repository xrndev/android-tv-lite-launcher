import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # para importar fake_adb

from tvlite import android  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_home(request, tmp_path, monkeypatch):
    """Backups y descargas van a una carpeta temporal. En las pruebas unitarias las esperas no
    duermen (FakeAdb es determinista); en las de integracion con emulador real se espera de verdad."""
    monkeypatch.setenv("TVLITE_HOME", str(tmp_path / "tvlite-home"))
    if "integration" not in Path(str(request.node.fspath)).parts:
        monkeypatch.setattr(android, "wait_for", lambda predicate, timeout=0, interval=0: bool(predicate()))
    return tmp_path


@pytest.fixture
def apk(tmp_path):
    path = tmp_path / "litelauncher.apk"
    path.write_bytes(b"fake")
    return path
