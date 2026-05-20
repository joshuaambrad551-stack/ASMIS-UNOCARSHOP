"""
main.py
UnoCarshop ASMIS — Application Entry Point
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from modules.login import LoginWindow


def main():
    # High-DPI attributes must be set before QApplication is created.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("UnoCarshop ASMIS")
    app.setOrganizationName("UnoCarshop")

    # Global font scaling
    font = QFont("Segoe UI", 11)
    app.setFont(font)
    app.setStyleSheet("""
        QLabel { font-size: 14px; }
        QPushButton { font-size: 14px; min-height: 40px; }
        QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            font-size: 14px;
            min-height: 38px;
        }
        QTableWidget { font-size: 14px; }
        QHeaderView::section { font-size: 12px; }
    """)

    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

