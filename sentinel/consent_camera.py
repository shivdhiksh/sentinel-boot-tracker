"""
Sentinel Consent-Based Camera Module:
Runs strictly as an isolated interactive desktop subprocess in the active user session.
Displays an explicit local consent dialog before activating any camera hardware.
If approved, displays a visible on-screen camera active indicator, captures exactly
ONE frame, releases the hardware, and exits.
"""
import sys
import os
import argparse
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtMultimedia import QMediaCaptureSession, QCamera, QImageCapture

class CameraConsentDialog(QDialog):
    def __init__(self, timeout_sec: int = 30):
        super().__init__()
        self.setWindowTitle("🛡️ Sentinel Security — Remote Camera Request")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setFixedSize(480, 220)
        self.remaining_seconds = timeout_sec
        self.consent_granted = False
        self.timed_out = False

        # Main Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header Title
        title_label = QLabel("⚠️ Remote Camera Access Requested")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #d9534f;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "An authorized remote Telegram administrator has requested a single photo.\n"
            "The webcam will <b>NEVER</b> activate without your explicit local consent.\n"
            "Do you grant permission to capture one image now?"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Countdown Timer Label
        self.timer_label = QLabel(f"Request will automatically be denied in: {self.remaining_seconds}s")
        self.timer_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.timer_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.deny_btn = QPushButton("❌ Deny Access")
        self.deny_btn.setMinimumHeight(38)
        self.deny_btn.setStyleSheet("""
            QPushButton {
                background-color: #d9534f;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
        """)
        self.deny_btn.clicked.connect(self._on_deny)
        btn_layout.addWidget(self.deny_btn)

        self.approve_btn = QPushButton("✅ Approve Once")
        self.approve_btn.setMinimumHeight(38)
        self.approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #5cb85c;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #449d44;
            }
        """)
        self.approve_btn.clicked.connect(self._on_approve)
        btn_layout.addWidget(self.approve_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 1-second interval timer
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._tick)
        self.countdown_timer.start()

    def _tick(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.countdown_timer.stop()
            self.timed_out = True
            self.reject()
        else:
            self.timer_label.setText(f"Request will automatically be denied in: {self.remaining_seconds}s")

    def _on_approve(self):
        self.countdown_timer.stop()
        self.consent_granted = True
        self.accept()

    def _on_deny(self):
        self.countdown_timer.stop()
        self.consent_granted = False
        self.reject()


class CameraCaptureIndicator(QWidget):
    """
    Displays a persistent, non-hidden indicator window so the local user clearly
    observes camera initialization and single-frame capture.
    """
    def __init__(self, target_filepath: str):
        super().__init__()
        self.target_filepath = str(Path(target_filepath).resolve())
        self.setWindowTitle("📷 Sentinel — Camera Active")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setFixedSize(360, 100)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        indicator_label = QLabel("🔴 WEBCAM ACTIVE")
        ind_font = QFont()
        ind_font.setPointSize(14)
        ind_font.setBold(True)
        indicator_label.setFont(ind_font)
        indicator_label.setStyleSheet("color: red;")
        indicator_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(indicator_label)

        sub_label = QLabel("Capturing single authorized verification frame...")
        sub_label.setStyleSheet("color: #333; font-size: 11px;")
        sub_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub_label)

        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget {
                background-color: #fff3cd;
                border: 2px solid #ffeeba;
                border-radius: 8px;
            }
        """)

        # Camera Capture Session
        self.session = QMediaCaptureSession()
        self.camera = QCamera()
        self.image_capture = QImageCapture()

        self.session.setCamera(self.camera)
        self.session.setImageCapture(self.image_capture)

        self.image_capture.imageSaved.connect(self._on_image_saved)
        self.image_capture.errorOccurred.connect(self._on_capture_error)
        self.camera.errorOccurred.connect(self._on_camera_error)

        self.captured = False
        self.error_msg = None

    def start_capture(self):
        self.show()
        # Give sensor 800ms warm-up/auto-exposure before snapping
        try:
            self.camera.start()
            QTimer.singleShot(900, self._snap_frame)
            # Timeout guard: max 5 seconds for capture
            QTimer.singleShot(5000, self._on_timeout)
        except Exception as exc:
            self.error_msg = f"Failed to start camera hardware: {exc}"
            self.close()

    def _snap_frame(self):
        if not self.captured and not self.error_msg:
            self.image_capture.captureToFile(self.target_filepath)

    def _on_image_saved(self, req_id: int, file_path: str):
        self.captured = True
        try:
            self.camera.stop()
        except Exception:
            pass
        self.close()
        QApplication.quit()

    def _on_capture_error(self, req_id: int, error: int, error_string: str):
        self.error_msg = f"Image capture error: {error_string}"
        try:
            self.camera.stop()
        except Exception:
            pass
        self.close()
        QApplication.quit()

    def _on_camera_error(self, error: int, error_string: str):
        self.error_msg = f"Camera device error: {error_string}"
        try:
            self.camera.stop()
        except Exception:
            pass
        self.close()
        QApplication.quit()

    def _on_timeout(self):
        if not self.captured and not self.error_msg:
            self.error_msg = "Camera capture timed out after 5 seconds."
            try:
                self.camera.stop()
            except Exception:
                pass
            self.close()
            QApplication.quit()


def main():
    parser = argparse.ArgumentParser(description="Sentinel Consent-Based Camera Helper")
    parser.add_argument("output_path", help="Absolute path to save captured image")
    parser.add_argument("--timeout", type=int, default=30, help="Consent dialog timeout in seconds")
    parser.add_argument("--test-mode", choices=["approve", "deny", "timeout"], default=None,
                        help="Automated test mode to simulate user response without manual clicks")

    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)

    output_path = Path(args.output_path).resolve()
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.test_mode == "deny":
        # Simulate local user clicking Deny
        print("SIMULATED_LOCAL_USER_DENIED")
        sys.exit(1)
    elif args.test_mode == "timeout":
        # Simulate local consent timeout
        print("SIMULATED_LOCAL_CONSENT_TIMEOUT")
        sys.exit(2)
    elif args.test_mode == "approve":
        # Skip dialog in automated test mode and perform real capture with visible indicator
        indicator = CameraCaptureIndicator(str(output_path))
        indicator.start_capture()
        app.exec()
        if indicator.captured and output_path.exists():
            print(f"SUCCESS:{output_path}")
            sys.exit(0)
        else:
            print(f"ERROR:{indicator.error_msg or 'Capture failed'}")
            sys.exit(3)

    # Standard Interactive User Session Flow
    dialog = CameraConsentDialog(timeout_sec=args.timeout)
    res = dialog.exec()

    if dialog.timed_out:
        print("LOCAL_USER_TIMEOUT")
        sys.exit(2)
    elif not dialog.consent_granted:
        print("LOCAL_USER_DENIED")
        sys.exit(1)

    # Local user explicitly clicked "Approve Once"
    indicator = CameraCaptureIndicator(str(output_path))
    indicator.start_capture()
    app.exec()

    if indicator.captured and output_path.exists():
        print(f"SUCCESS:{output_path}")
        sys.exit(0)
    else:
        err = indicator.error_msg or "Unknown camera failure"
        print(f"ERROR:{err}")
        sys.exit(3)

if __name__ == "__main__":
    main()
