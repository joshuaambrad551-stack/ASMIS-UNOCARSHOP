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
from modules.widgets import (
    BORDER, NAVY, NAVY_HOVER, NAVY_PRESSED,
    PAGE_BG, RED, TEXT_DARK, TEXT_SOFT, friendly_error_text
)


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UnoCarshop ASMIS — Login")
        self.setFixedSize(440, 540)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {PAGE_BG};
                font-family: 'Segoe UI';
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(0)

        # ── Card ──────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 14px;
                border: 1px solid {BORDER};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 38, 34, 34)
        card_layout.setSpacing(14)

        # Badge
        badge = QLabel("ASMIS")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(30)
        badge.setStyleSheet("""
            background-color: #c1121f; color: white;
            font-weight: 700; font-size: 13px;
            border-radius: 6px; padding: 4px 10px;
        """)

        title = QLabel("UnoCarshop")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 23px; font-weight: 700; color: {TEXT_DARK}; border: none;")

        subtitle = QLabel("Auto Shop Management & Information System")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"font-size: 11px; color: {TEXT_SOFT}; border: none;")

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background: {BORDER}; border: none; max-height: 1px; margin: 4px 0;")

        # Username
        lbl_user = QLabel("USERNAME")
        lbl_user.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {TEXT_SOFT}; "
            "letter-spacing: 1px; border: none;"
        )

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Enter your username")
        self.input_username.setFixedHeight(42)
        self.input_username.setStyleSheet(self._field_style())

        # Password
        lbl_pass = QLabel("PASSWORD")
        lbl_pass.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {TEXT_SOFT}; "
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
        self.chk_show.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 12px; border: none;")
        self.chk_show.toggled.connect(
            lambda on: self.input_password.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )

        # Login button
        self.btn_login = QPushButton("Sign In")
        self.btn_login.setFixedHeight(44)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY}; color: white;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {NAVY_HOVER}; }}
            QPushButton:pressed {{ background-color: {NAVY_PRESSED}; }}
            QPushButton:disabled {{ background-color: #7d8794; }}
        """)
        self.btn_login.clicked.connect(self._handle_login)

        # Error label
        self.lbl_error = QLabel("")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet(f"color: {RED}; font-size: 12px; border: none;")

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
        footer.setStyleSheet("font-size: 11px; color: #0b1f3a; margin-top: 14px;")

        main_layout.addStretch()
        main_layout.addWidget(card)
        main_layout.addWidget(footer)
        main_layout.addStretch()

    def _field_style(self):
        return f"""
            QLineEdit {{
                border: 1px solid {BORDER}; border-radius: 8px;
                padding: 0 12px; font-size: 13px; color: {TEXT_DARK}; background: #fff;
            }}
            QLineEdit:focus {{ border: 1px solid {NAVY}; }}
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
