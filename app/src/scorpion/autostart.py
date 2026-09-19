from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AutostartStatus:
    enabled: bool
    changed: bool
    path: Path | None
    detail: str


def _default_startup_dir() -> Path | None:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def ensure_windows_autostart(
    app_root: str | Path,
    *,
    enabled: bool = True,
    startup_dir: str | Path | None = None,
    platform_name: str | None = None,
) -> AutostartStatus:
    platform_name = platform_name or os.name
    if platform_name != "nt":
        return AutostartStatus(False, False, None, "Autostart ist nur unter Windows verfügbar.")

    root = Path(app_root).resolve()
    startup = Path(startup_dir) if startup_dir is not None else _default_startup_dir()
    if startup is None:
        return AutostartStatus(False, False, None, "Windows Startup-Ordner konnte nicht bestimmt werden.")

    launcher = startup / "Scorpion MK50.cmd"
    if not enabled:
        changed = launcher.exists()
        if changed:
            launcher.unlink()
        return AutostartStatus(False, changed, launcher, "Scorpion-Autostart ist deaktiviert.")

    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    run_bat = root / "run_scorpion.bat"
    if not run_bat.exists():
        return AutostartStatus(False, False, launcher, "run_scorpion.bat fehlt.")

    startup.mkdir(parents=True, exist_ok=True)
    content = (
        "@echo off\n"
        f'cd /d "{root}"\n'
        f'set "PYTHONPATH={root / "src"}"\n'
        f'start "" /min "{pythonw}" -m scorpion\n'
    )
    previous = launcher.read_text(encoding="utf-8") if launcher.exists() else None
    changed = previous != content
    if changed:
        launcher.write_text(content, encoding="utf-8")
    return AutostartStatus(True, changed, launcher, "Scorpion startet beim Windows-Login automatisch.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure Scorpion MK50 Windows autostart.")
    parser.add_argument("--app-root", default=".")
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args(argv)
    status = ensure_windows_autostart(args.app_root, enabled=not args.disable)
    print(status.detail)
    return 0 if status.enabled or args.disable else 1


if __name__ == "__main__":
    raise SystemExit(main())
