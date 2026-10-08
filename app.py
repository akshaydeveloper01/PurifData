import sys
import os

import pandas as pd

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QGroupBox,
    QFileDialog
)


class PurifDataApp(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("PurifData")
        self.resize(1100, 700)

        # Main window
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # Project title
        title = QLabel("PurifData")
        title.setStyleSheet(
            "font-size: 32px; font-weight: bold;"
        )

        subtitle = QLabel(
            "AI-Driven Data Cleaning and Quality Assessment"
        )
        subtitle.setStyleSheet("font-size: 16px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # File selection
        file_box = QGroupBox("Dataset Selection")
        file_layout = QVBoxLayout()

        file_text = QLabel("Select a CSV or Excel file:")

        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("No file selected")
        self.file_path.setReadOnly(True)

        browse_btn = QPushButton("Browse File")
        browse_btn.clicked.connect(self.select_file)

        file_layout.addWidget(file_text)
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(browse_btn)

        file_box.setLayout(file_layout)

        layout.addWidget(file_box)

        # Security section
        check_box = QGroupBox("Security & File Validation")
        check_layout = QVBoxLayout()

        self.check_status = QLabel(
            "Waiting for file selection..."
        )

        check_layout.addWidget(self.check_status)

        check_box.setLayout(check_layout)

        layout.addWidget(check_box)

        layout.addStretch()

    # Select CSV or Excel file
    def select_file(self):

        file_name, file_type = QFileDialog.getOpenFileName(
            self,
            "Select Dataset",
            "",
            "Dataset Files (*.csv *.xlsx *.xls)"
        )

        if file_name:
            self.file_path.setText(file_name)
            self.validate_file(file_name)

    # Check whether the selected file is safe to process
    def validate_file(self, file_name):

        # Check 1: File exists
        if not os.path.isfile(file_name):
            self.check_status.setText(
                "File validation failed: File does not exist."
            )
            return

        # Check 2: Check file extension
        extension = os.path.splitext(file_name)[1].lower()

        allowed_files = [".csv", ".xlsx", ".xls"]

        if extension not in allowed_files:
            self.check_status.setText(
                "File validation failed: Unsupported file type."
            )
            return

        # Check 3: Check file size
        file_size = os.path.getsize(file_name)

        max_size = 50 * 1024 * 1024

        if file_size > max_size:
            self.check_status.setText(
                "File validation failed: File is larger than 50 MB."
            )
            return

        # Check 4: Check filename
        file_name_only = os.path.basename(file_name)

        if not file_name_only.strip():
            self.check_status.setText(
                "File validation failed: Invalid filename."
            )
            return

        # Check 5: Try reading the file
        try:

            if extension == ".csv":
                pd.read_csv(file_name, nrows=5)

            elif extension == ".xlsx":
                pd.read_excel(file_name, nrows=5)

            elif extension == ".xls":
                pd.read_excel(file_name, nrows=5, engine="xlrd")

        except Exception:
            self.check_status.setText(
                "File validation failed: File cannot be read."
            )
            return

        # All checks passed
        self.check_status.setText(
            "File validation successful. File is ready for processing."
        )


def main():

    app = QApplication(sys.argv)

    window = PurifDataApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()