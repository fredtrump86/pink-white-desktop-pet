from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from desktop_pet.config import APP_NAME


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        arguments = [sys.executable]
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        interpreter = pythonw if pythonw.exists() else Path(sys.executable)
        entrypoint = Path(__file__).resolve().parent.parent / "app.py"
        arguments = [str(interpreter), str(entrypoint)]
    return subprocess.list2cmdline([str(argument) for argument in arguments])


def set_start_with_windows(enabled: bool) -> None:
    if os.name != "nt":
        raise RuntimeError("开机启动设置仅支持 Windows")

    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                APP_NAME,
                0,
                winreg.REG_SZ,
                _startup_command(),
            )
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def is_start_with_windows() -> bool:
    if os.name != "nt":
        return False

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
    except FileNotFoundError:
        return False
    return True

