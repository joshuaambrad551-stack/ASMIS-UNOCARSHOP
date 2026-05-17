"""
modules/login.py
UnoCarshop ASMIS — Login Window
"""
import sys
import os
import hashlib

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection
from modules.widgets import friendly_error_text


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UnoCarshop ASMIS — Login")
        self.setFixedSize(440, 540)
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f4f0;
                font-family: 'Segoe UI';
            }
        """)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(0)

        # ── Card ──────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 14px;
                border: 1px solid #e0ddd5;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 38, 34, 34)
        card_layout.setSpacing(14)

        # Badge
        badge = QLabel("ASMIS")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(30)
        badge.setStyleSheet("""
            background-color: #f5a623; color: white;
            font-weight: 700; font-size: 13px;
            border-radius: 6px; padding: 4px 10px;
        """)

        title = QLabel("UnoCarshop")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 23px; font-weight: 700; color: #1a1a18; border: none;")

        subtitle = QLabel("Auto Shop Management & Information System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 11px; color: #888780; border: none;")

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background: #e0ddd5; border: none; max-height: 1px; margin: 4px 0;")

        # Username
        lbl_user = QLabel("USERNAME")
        lbl_user.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #888780; "
            "letter-spacing: 1px; border: none;"
        )

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Enter your username")
        self.input_username.setFixedHeight(42)
        self.input_username.setStyleSheet(self._field_style())

        # Password
        lbl_pass = QLabel("PASSWORD")
        lbl_pass.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #888780; "
            "letter-spacing: 1px; border: none;"
        )

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Enter your password")
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setFixedHeight(42)
        self.input_password.setStyleSheet(self._field_style())
        self.input_password.returnPressed.connect(self._handle_login)

        # Show password toggle
        self.chk_show = QCheckBox("Show password")
        self.chk_show.setStyleSheet("color: #888780; font-size: 12px; border: none;")
        self.chk_show.toggled.connect(
            lambda on: self.input_password.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )

        # Login button
        self.btn_login = QPushButton("Sign In")
        self.btn_login.setFixedHeight(44)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #f5a623; color: white;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }
            QPushButton:hover { background-color: #e08e0b; }
            QPushButton:pressed { background-color: #c97d0a; }
            QPushButton:disabled { background-color: #ddd; }
        """)
        self.btn_login.clicked.connect(self._handle_login)

        # Error label
        self.lbl_error = QLabel("")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet("color: #A32D2D; font-size: 12px; border: none;")

        card_layout.addWidget(badge)
        card_layout.addSpacing(2)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(divider)
        card_layout.addSpacing(2)
        card_layout.addWidget(lbl_user)
        card_layout.addWidget(self.input_username)
        card_layout.addWidget(lbl_pass)
        card_layout.addWidget(self.input_password)
        card_layout.addWidget(self.chk_show)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.btn_login)
        card_layout.addWidget(self.lbl_error)

        footer = QLabel("© 2026 UnoCarshop. All rights reserved.")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #aaa; margin-top: 14px;")

        main_layout.addStretch()
        main_layout.addWidget(card)
        main_layout.addWidget(footer)
        main_layout.addStretch()

    def _field_style(self):
        return """
            QLineEdit {
                border: 1px solid #e0ddd5; border-radius: 8px;
                padding: 0 12px; font-size: 13px; color: #1a1a18; background: #fff;
            }
            QLineEdit:focus { border: 1px solid #aaa; }
        """

    def _handle_login(self):
        username = self.input_username.text().strip()
        password = self.input_password.text().strip()

        if not username or not password:
            self.lbl_error.setText("⚠  Please enter username and password.")
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText("Signing in…")
        hashed = hashlib.sha256(password.encode()).hexdigest()

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT u.user_id, u.full_name, r.role_name, r.permissions
                FROM users u
                JOIN roles r ON u.role_id = r.role_id
                WHERE u.username = %s AND u.password_hash = %s AND u.is_active = TRUE
            """, (username, hashed))
            user = cur.fetchone()
            conn.close()

            if user:
                self.lbl_error.setText("")
                self._open_main(user)
            else:
                self.lbl_error.setText("❌  Invalid username or password.")
        except Exception as e:
            print(f"Login database error: {e}", file=sys.stderr)
            self.lbl_error.setText(friendly_error_text("Login Error", e))
        finally:
            self.btn_login.setEnabled(True)
            self.btn_login.setText("Sign In")

    def _open_main(self, user):
        from modules.main_window import MainWindow
        self.main_win = MainWindow(user)
        self.main_win.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = LoginWindow()
    w.show()
    sys.exit(app.exec_())
