from __future__ import annotations

import ctypes
import os


ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\PinkWhiteDesktopPet_21B7965A"


class AlreadyRunningError(RuntimeError):
    pass


class SingleInstance:
    def __init__(self) -> None:
        self._handle: int | None = None

    def acquire(self) -> None:
        if os.name != "nt":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            raise OSError("无法创建桌宠单实例锁")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise AlreadyRunningError("粉白桌宠已经在运行")
        self._handle = handle

    def release(self) -> None:
        if self._handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

