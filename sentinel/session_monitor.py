"""
Native Win32 Session Monitor Daemon:
Listens for Windows Session Lock and Unlock events using WTSRegisterSessionNotification.
Zero polling, 0% CPU consumption, with 64-bit Win32 ABI compliance, single-instance mutex, and clean shutdown.
"""
import os
import sys
import time
import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from .config import BASE_DIR, logger, sanitize
from .telegram import send_telegram_alert

# Win32 Constants
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0
ERROR_ALREADY_EXISTS = 183
WS_EX_TOOLWINDOW = 0x00000080
WS_POPUP = 0x80000000

# 64-bit Win32 Types
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_size_t

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    WPARAM,
    LPARAM
)

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]

# Setup Win32 Function Signatures (64-bit ABI Compliant)
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
wtsapi32 = ctypes.windll.wtsapi32

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
wtsapi32.WTSRegisterSessionNotification.restype = wintypes.BOOL

wtsapi32.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
wtsapi32.WTSUnRegisterSessionNotification.restype = wintypes.BOOL

kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

class SessionMonitor:
    def __init__(self):
        self.hwnd: Optional[int] = None
        self.mutex: Optional[int] = None
        self.last_state: Optional[str] = None
        self.running = False
        self._wnd_proc_ref = None

    def _acquire_mutex(self) -> bool:
        """Ensures only a single instance of the session monitor runs per user session."""
        username = os.getenv("USERNAME", "DefaultUser")
        mutex_name = f"SentinelSessionMonitor_{username}"
        self.mutex = kernel32.CreateMutexW(None, True, mutex_name)
        if ctypes.GetLastError() == ERROR_ALREADY_EXISTS:
            logger.info("Sentinel Session Monitor is already active in this session.")
            return False
        return True

    def _window_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            if msg == WM_WTSSESSION_CHANGE:
                if wparam == WTS_SESSION_LOCK:
                    if self.last_state != "lock":
                        self.last_state = "lock"
                        try:
                            send_telegram_alert("lock")
                        except Exception as exc:
                            logger.error(f"Error dispatching lock notification: {sanitize(str(exc))}")
                elif wparam == WTS_SESSION_UNLOCK:
                    if self.last_state != "unlock":
                        self.last_state = "unlock"
                        try:
                            send_telegram_alert("unlock")
                        except Exception as exc:
                            logger.error(f"Error dispatching unlock notification: {sanitize(str(exc))}")
                return 0
        except Exception as exc:
            logger.error(f"Error in Win32 window procedure: {sanitize(str(exc))}")
        
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def start(self):
        """Initializes the Win32 message window and starts the event loop."""
        if not self._acquire_mutex():
            logger.info("Mutex acquisition returned False, exiting.")
            return

        self.running = True
        h_inst = kernel32.GetModuleHandleW(None)
        class_name = f"SentinelSessionMonitorClass_{int(time.time())}"

        self._wnd_proc_ref = WNDPROC(self._window_proc)

        wnd_class = WNDCLASSEXW()
        wnd_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wnd_class.style = 0
        wnd_class.lpfnWndProc = self._wnd_proc_ref
        wnd_class.cbClsExtra = 0
        wnd_class.cbWndExtra = 0
        wnd_class.hInstance = h_inst
        wnd_class.hIcon = None
        wnd_class.hCursor = None
        wnd_class.hbrBackground = None
        wnd_class.lpszMenuName = None
        wnd_class.lpszClassName = class_name
        wnd_class.hIconSm = None

        reg_res = user32.RegisterClassExW(ctypes.byref(wnd_class))
        if not reg_res:
            err = ctypes.GetLastError()
            logger.error(f"Failed to register Win32 window class (Error: {err})")
            return

        # Create a top-level hidden tool window for WTS session notifications
        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW,
            class_name,
            "SentinelSessionMonitorWindow",
            WS_POPUP,
            0, 0, 0, 0,
            None,
            None,
            h_inst,
            None
        )

        if not self.hwnd:
            err = ctypes.GetLastError()
            logger.error(f"Failed to create Win32 message window (Error: {err})")
            return

        # Register for WTS session notifications
        wts_res = wtsapi32.WTSRegisterSessionNotification(
            self.hwnd,
            NOTIFY_FOR_THIS_SESSION
        )
        if not wts_res:
            err = ctypes.GetLastError()
            logger.error(f"Failed to register WTS session notifications (Error: {err})")
            return

        logger.info(f"Sentinel Session Monitor daemon active. HWND: {self.hwnd}")

        msg = wintypes.MSG()
        while self.running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res == 0:  # WM_QUIT
                logger.error("GetMessageW received WM_QUIT")
                break
            elif res == -1:
                logger.error(f"GetMessage error: {ctypes.GetLastError()}")
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        logger.error("SessionMonitor loop terminated.")

        # Cleanup on termination
        if self.hwnd:
            wtsapi32.WTSUnRegisterSessionNotification(self.hwnd)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self.mutex:
            kernel32.CloseHandle(self.mutex)
            self.mutex = None

    def stop(self):
        """Stops the event loop."""
        self.running = False
        if self.hwnd:
            user32.PostMessageW(self.hwnd, 0x0012, 0, 0)  # WM_QUIT

def ensure_session_monitor_running():
    """
    Spawns session_monitor silently in background using the proven silent_runner wrapper.
    """
    try:
        vbs_path = BASE_DIR / "silent_runner.vbs"
        if vbs_path.exists():
            subprocess.Popen(
                ["wscript.exe", str(vbs_path), "session_monitor"],
                cwd=str(BASE_DIR),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
            if not Path(pythonw_path).exists():
                pythonw_path = "pythonw.exe"
            script_path = str(BASE_DIR / "power_monitor.py")
            subprocess.Popen(
                [pythonw_path, script_path, "session_monitor"],
                cwd=str(BASE_DIR),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
    except Exception as exc:
        logger.warning(f"Could not auto-start session monitor: {sanitize(str(exc))}")

def run_session_monitor():
    monitor = SessionMonitor()
    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.stop()

if __name__ == "__main__":
    run_session_monitor()
