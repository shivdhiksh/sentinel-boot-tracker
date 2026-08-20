"""
Native Win32 Session Monitor Daemon:
Listens for Windows Session Lock and Unlock events using WTSRegisterSessionNotification.
Zero polling, 0% CPU consumption, with duplicate prevention and clean shutdown.
"""
import sys
import time
import signal
import ctypes
from ctypes import wintypes
from typing import Optional

from .config import logger
from .telegram import send_telegram_alert

# Win32 Constants
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0
PM_REMOVE = 0x0001
WS_EX_TOOLWINDOW = 0x00000080
WS_POPUP = 0x80000000

# Window Proc Callback Type
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
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

class SessionMonitor:
    def __init__(self):
        self.hwnd: Optional[int] = None
        self.last_state: Optional[str] = None
        self.running = False
        self._wnd_proc_ref = None  # Prevent GC of ctypes callback

    def _window_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:
                if self.last_state != "lock":
                    self.last_state = "lock"
                    print("[*] Detected Workstation Lock event. Sending Telegram alert...")
                    try:
                        send_telegram_alert("lock")
                    except Exception as exc:
                        logger.error(f"Error handling lock notification: {exc}")
            elif wparam == WTS_SESSION_UNLOCK:
                if self.last_state != "unlock":
                    self.last_state = "unlock"
                    print("[*] Detected Workstation Unlock event. Sending Telegram alert...")
                    try:
                        send_telegram_alert("unlock")
                    except Exception as exc:
                        logger.error(f"Error handling unlock notification: {exc}")
            return 0
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def start(self):
        """Initializes the Win32 message-only window and starts the event loop."""
        self.running = True
        h_inst = ctypes.windll.kernel32.GetModuleHandleW(None)
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

        reg_res = ctypes.windll.user32.RegisterClassExW(ctypes.byref(wnd_class))
        if not reg_res:
            err = ctypes.GetLastError()
            logger.error(f"Failed to register Win32 window class (Error: {err})")
            print(f"Error: Failed to register Win32 window class ({err})")
            return

        # Create hidden message window
        self.hwnd = ctypes.windll.user32.CreateWindowExW(
            WS_EX_TOOLWINDOW,
            class_name,
            "SentinelSessionMonitorWindow",
            WS_POPUP,
            0, 0, 0, 0,
            None, None, h_inst, None
        )

        if not self.hwnd:
            err = ctypes.GetLastError()
            logger.error(f"Failed to create Win32 message window (Error: {err})")
            print(f"Error: Failed to create Win32 message window ({err})")
            return

        # Register for WTS session notifications
        wts_res = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
            self.hwnd,
            NOTIFY_FOR_THIS_SESSION
        )
        if not wts_res:
            err = ctypes.GetLastError()
            logger.error(f"Failed to register WTS session notifications (Error: {err})")
            print(f"Error: Failed to register WTS notifications ({err})")
            return

        print("[*] Sentinel Session Monitor active. Listening for Lock/Unlock events...")

        msg = wintypes.MSG()
        while self.running:
            # GetMessage blocks until a message arrives with 0% CPU consumption
            res = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup on exit
        if self.hwnd:
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(self.hwnd)
            ctypes.windll.user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def stop(self):
        """Stops the event loop."""
        self.running = False
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, 0x0012, 0, 0)  # WM_QUIT

def run_session_monitor():
    monitor = SessionMonitor()

    def sig_handler(signum, frame):
        print("\n[*] Stopping Sentinel Session Monitor...")
        monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    monitor.start()

if __name__ == "__main__":
    run_session_monitor()
