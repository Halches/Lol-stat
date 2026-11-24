"""GitHub stable releases and a shell-free, rollback-capable Windows updater."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from uuid import uuid4
from .app_version import VERSION

REPO = "Halches/Lol-stat"
RELEASES_URL = f"https://github.com/{REPO}/releases"
API_URL = f"https://api.github.com/repos/{REPO}/releases"
ASSET_NAME = "LoLHelper.exe"
CHECK_SECONDS = 15 * 60
MAX_DOWNLOAD = 512 * 1024 * 1024


class UpdateError(Exception):
    pass


def current_version():
    return VERSION


def version_number(tag):
    match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", str(tag))
    return tuple(map(int, match.groups())) if match else None


def release_asset_url(tag, name):
    return f"{RELEASES_URL}/download/{tag}/{name}"


def open_download(url, timeout=15):
    return urlopen(Request(url, headers={"User-Agent": "LoLHelper-Updater/1",
                                        "Accept": "application/vnd.github+json" if url.startswith(API_URL) else "*/*",
                                        "X-GitHub-Api-Version": "2022-11-28"}), timeout=timeout)


@dataclass(frozen=True)
class Release:
    version: str
    title: str
    notes: str
    published: str
    url: str
    download: str | None
    size: int
    digest: str | None
    checksum_url: str | None


def parse_release(raw):
    if not isinstance(raw, dict) or raw.get("draft") or raw.get("prerelease"):
        return None
    tag = raw.get("tag_name")
    if version_number(tag) is None:
        return None
    assets = raw.get("assets", [])
    assets = assets if isinstance(assets, list) else []
    asset = next((a for a in assets if isinstance(a, dict) and a.get("name") == ASSET_NAME
                  and a.get("state", "uploaded") == "uploaded"), {})
    url = asset.get("browser_download_url")
    url = url if url == release_asset_url(tag, ASSET_NAME) else None
    size = asset.get("size", 0)
    size = size if type(size) is int and 0 < size <= MAX_DOWNLOAD else 0
    digest = asset.get("digest", "")
    digest = digest[7:].lower() if isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest) else None
    checksums = release_asset_url(tag, "SHA256SUMS.txt")
    checksum_url = next((checksums for a in assets if isinstance(a, dict)
                         and a.get("name") == "SHA256SUMS.txt" and a.get("browser_download_url") == checksums), None)
    return Release(tag, str(raw.get("name") or tag), str(raw.get("body") or "Описание выпуска пока не добавлено."),
                   str(raw.get("published_at") or "")[:10], f"{RELEASES_URL}/tag/{tag}",
                   url if size else None, size, digest, checksum_url)


def fetch_releases():
    releases = {}
    # Service tags such as voices and silero must not hide application releases.
    for page in range(1, 4):
        with open_download(f"{API_URL}?per_page=30&page={page}") as response:
            payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise UpdateError("Слишком большой ответ GitHub.")
        rows = json.loads(payload)
        if not isinstance(rows, list):
            raise UpdateError("GitHub вернул неожиданный ответ.")
        for raw in rows:
            release = parse_release(raw)
            if release:
                releases[release.version] = release
        if len(releases) >= 3 or len(rows) < 30:
            break
    return sorted(releases.values(), key=lambda r: version_number(r.version), reverse=True)[:3]


def note_excerpt(text, limit=650, lines=9):
    text = text.strip()
    preview = "\n".join(text.splitlines()[:lines])[:limit].rstrip()
    shortened = preview != text
    return preview + ("…" if shortened else ""), shortened


def expected_digest(release):
    if release.digest:
        return release.digest
    if release.checksum_url:
        with open_download(release.checksum_url) as response:
            payload = response.read(65_537)
        if len(payload) <= 65_536:
            for line in payload.decode("utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip("*") == ASSET_NAME and re.fullmatch(r"[a-fA-F0-9]{64}", parts[0]):
                    return parts[0].lower()
    raise UpdateError("У выпуска нет контрольной суммы. Откройте выпуск на GitHub.")


def verify_file(path, digest, size):
    hasher = sha256()
    with Path(path).open("rb") as file:
        if file.read(2) != b"MZ":
            raise UpdateError("Полученный файл не является Windows-приложением.")
        file.seek(0)
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    if Path(path).stat().st_size != size or hasher.hexdigest() != digest:
        raise UpdateError("Проверка файла обновления не пройдена. Скачайте его повторно.")


def update_root():
    return Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "LoLHelper" / "updates"


def download_release(release, progress=lambda _got, _total: None):
    if not release.download or release.download != release_asset_url(release.version, ASSET_NAME):
        raise UpdateError("Файл обновления для Windows пока не опубликован.")
    digest = expected_digest(release)
    folder = update_root() / uuid4().hex
    folder.mkdir(parents=True)
    target = folder / "new.exe"
    partial = folder / "new.part"
    try:
        got = 0
        with open_download(release.download, timeout=30) as response, partial.open("xb") as file:
            while chunk := response.read(256 * 1024):
                got += len(chunk)
                if got > release.size or got > MAX_DOWNLOAD:
                    raise UpdateError("Размер обновления не совпадает с выпуском.")
                file.write(chunk)
                progress(got, release.size)
        verify_file(partial, digest, release.size)
        partial.replace(target)
        return {"folder": str(folder), "candidate": str(target), "digest": digest,
                "size": release.size, "version": release.version}
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def clean_environment():
    env = {key: value for key, value in os.environ.items() if not key.startswith(("_PYI", "_MEI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def launch_installer(download, *, target=None, parent_pid=None, restart_args=()):
    if not getattr(sys, "frozen", False):
        raise UpdateError("Установка доступна в собранном EXE. Из исходников откройте выпуск на GitHub.")
    target = Path(target or sys.executable).resolve()
    folder = Path(download["folder"]).resolve() / ("install-" + uuid4().hex)
    folder.mkdir()
    verify_file(download["candidate"], download["digest"], download["size"])
    # Check permissions before closing the old application.
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".lolhelper-write-", delete=True):
        pass
    helper = folder / "installer.exe"
    shutil.copy2(sys.executable, helper)
    candidate = folder / "new.exe"
    shutil.copy2(download["candidate"], candidate)
    manifest = dict(download, folder=str(folder), candidate=str(candidate), target=str(target),
                    parent_pid=parent_pid or os.getpid(), args=list(restart_args))
    manifest_path = folder / "transaction.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    process = subprocess.Popen([str(helper), "--apply-update", str(manifest_path)], env=clean_environment(),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(300):
        if (folder / "ready").exists():
            return folder
        if process.poll() is not None:
            error = folder / "error.txt"
            raise UpdateError(error.read_text(encoding="utf-8") if error.exists() else "Не удалось запустить установку.")
        time.sleep(.1)
    (folder / "cancel").touch()
    raise UpdateError("Установка не ответила. Приложение продолжает работать; попробуйте ещё раз.")


def wait_for_parent(pid, folder, seconds=120):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # The process has already exited.
            return
        raise UpdateError("Не удалось дождаться закрытия программы.")
    try:
        for _ in range(seconds * 4):
            if (folder / "cancel").exists():
                raise UpdateError("Установка отменена.")
            if kernel.WaitForSingleObject(handle, 250) == 0:
                return
        raise UpdateError("Приложение ещё открыто. Закройте его и повторите обновление.")
    finally:
        kernel.CloseHandle(handle)


def replace_and_restart(manifest, *, launch=None):
    """Transaction is also tested with ordinary files and a fake launcher."""
    target = Path(manifest["target"])
    candidate = Path(manifest["candidate"])
    backup = Path(manifest["folder"]) / "previous.exe"
    verify_file(candidate, manifest["digest"], manifest["size"])
    # Stage on the target volume: the update cache and portable EXE can be on
    # different drives (e.g. LocalAppData on C: and the application on W:).
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".lolhelper-update-", suffix=".exe", delete=False) as file:
        staged = Path(file.name)
    try:
        shutil.copy2(candidate, staged)
        verify_file(staged, manifest["digest"], manifest["size"])
        shutil.copy2(target, backup)
        # PyInstaller's bootstrap may briefly hold the EXE after the UI exits.
        for attempt in range(120):
            try:
                os.replace(staged, target)
                break
            except PermissionError:
                if attempt == 119:
                    raise UpdateError("Файл приложения занят. Предыдущая версия сохранена.")
                time.sleep(.5)
        process = None
        try:
            process = (launch or subprocess.Popen)([str(target), *manifest.get("args", []),
                                                   "--update-receipt", manifest["folder"]],
                                                  env=clean_environment(), cwd=str(target.parent))
            if launch is None:
                for _ in range(300):
                    if (Path(manifest["folder"]) / "started").exists():
                        return
                    if process.poll() is not None:
                        raise UpdateError("Новая версия завершилась при запуске.")
                    time.sleep(.1)
                raise UpdateError("Новая версия не подтвердила запуск.")
        except Exception:
            if launch is None and process is not None and process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            shutil.copy2(backup, staged)
            for attempt in range(120):
                try:
                    os.replace(staged, target)
                    break
                except PermissionError:
                    if attempt == 119:
                        raise UpdateError(f"Не удалось восстановить EXE. Предыдущая версия сохранена: {backup}")
                    time.sleep(.5)
            raise UpdateError("Новая версия не запустилась. Восстановлена предыдущая версия.") from None
    finally:
        staged.unlink(missing_ok=True)


def confirm_startup():
    if "--update-receipt" not in sys.argv:
        return
    try:
        folder = Path(sys.argv[sys.argv.index("--update-receipt") + 1]).resolve()
        manifest = json.loads((folder / "transaction.json").read_text(encoding="utf-8"))
        if folder.is_relative_to(update_root().resolve()) and Path(manifest["target"]).resolve() == Path(sys.executable).resolve():
            (folder / "started").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    except (OSError, ValueError, KeyError, IndexError):
        pass


def apply_update(manifest_path):
    folder = Path(manifest_path).resolve().parent
    parent_closed = False
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if Path(manifest["folder"]).resolve() != folder or Path(manifest["candidate"]).resolve().parent != folder:
            raise UpdateError("Некорректные пути обновления.")
        verify_file(manifest["candidate"], manifest["digest"], manifest["size"])
        (folder / "ready").touch()
        wait_for_parent(manifest["parent_pid"], folder)
        parent_closed = True
        if (folder / "cancel").exists():
            raise UpdateError("Установка отменена.")
        replace_and_restart(manifest)
        (folder / "complete").touch()
        return 0
    except Exception as error:
        (folder / "error.txt").write_text(str(error), encoding="utf-8")
        if parent_closed and not (folder / "cancel").exists():
            try:
                subprocess.Popen([manifest["target"], "--update-failed", str(folder)], env=clean_environment(),
                                 cwd=str(Path(manifest["target"]).parent))
            except OSError:
                pass
        return 1


def last_update_error():
    if "--update-failed" in sys.argv:
        try:
            folder = Path(sys.argv[sys.argv.index("--update-failed") + 1]).resolve()
            if folder.is_relative_to(update_root().resolve()):
                return (folder / "error.txt").read_text(encoding="utf-8")[:600]
        except (OSError, IndexError, ValueError):
            pass
    return None
