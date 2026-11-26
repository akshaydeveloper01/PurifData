import sys
import os
import re
import pandas as pd

from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame,
    QFileDialog, QPlainTextEdit,
    QScrollArea, QSizePolicy,
    QMessageBox, QInputDialog
)

from PySide6.QtCore import Qt, QThread, Signal

from ai_analysis import (
    analyze_quality_issues,
    get_api_key,
    save_api_key
)

from cleaning_plan import generate_cleaning_plan
from cleaning_preview import generate_cleaning_preview
from cleaning_engine import clean_dataset, read_original_dataset
from correction_dialogs import ManualCorrectionDialog

from db_manager import (
    initialize_database,
    create_session,
    log_event,
    update_session,
    save_report,
    complete_session
)


# --------------------------------------------------
# GEMINI BACKGROUND WORKER
# --------------------------------------------------

class AIAnalysisWorker(QThread):

    finished_signal = Signal(str)

    def __init__(self, issue_summary, dataset_profile):

        super().__init__()

        self.issue_summary = issue_summary
        self.dataset_profile = dataset_profile

    def run(self):

        try:

            result = analyze_quality_issues(
                self.issue_summary,
                self.dataset_profile
            )

            self.finished_signal.emit(result)

        except Exception as error:

            self.finished_signal.emit(
                f"Gemini analysis failed: {error}"
            )


# --------------------------------------------------
# MAIN APPLICATION
# --------------------------------------------------

class PurifDataApp(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "PurifData - Data Quality Platform"
        )

        self.resize(1100, 1250)
        self.setMinimumSize(750, 650)

        self.issue_summary = []
        self.dataset_profile = {}
        self.cleaning_plan = []

        self.manual_corrections = {
            "missing_changes": [],
            "duplicate_rows": [],
            "inconsistency_changes": []
        }

        self.manual_corrections_approved = False
        self.preview_generated = False

        self.ai_worker = None

        self.current_session_id = None
        self.assessment_completed = False

        self.cleaning_result = None
        self.comparison_result = None

        self.final_report_path = None
        self.final_report_content = None
        self.final_report_data = None

        try:

            initialize_database()

            print("Database connected successfully.")

        except Exception as error:

            print("Database initialization failed:", error)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #111827;
                color: #E5E7EB;
                font-family: Segoe UI;
                font-size: 10pt;
            }

            QFrame#card {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 12px;
            }

            QLabel#mainTitle {
                font-size: 30px;
                font-weight: bold;
                color: white;
            }

            QLabel#subtitle {
                font-size: 11px;
                color: #9CA3AF;
            }

            QLabel#sectionTitle {
                font-size: 17px;
                font-weight: bold;
                color: #F9FAFB;
            }

            QLabel#sectionNumber {
                color: #60A5FA;
                font-weight: bold;
            }

            QLineEdit, QPlainTextEdit {
                background-color: #111827;
                border: 1px solid #4B5563;
                border-radius: 7px;
                padding: 9px;
                color: #E5E7EB;
            }

            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 10px 15px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #1D4ED8;
            }

            QPushButton:disabled {
                background-color: #4B5563;
                color: #9CA3AF;
            }

            QScrollArea {
                border: none;
            }
        """)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.setCentralWidget(self.scroll_area)

        main_widget = QWidget()
        self.scroll_area.setWidget(main_widget)

        self.main_layout = QVBoxLayout(main_widget)

        self.main_layout.setContentsMargins(
            28, 24, 28, 28
        )

        self.main_layout.setSpacing(18)

        self.build_interface()

    # --------------------------------------------------
    # UI HELPERS
    # --------------------------------------------------

    def create_card(self):

        card = QFrame()
        card.setObjectName("card")

        card.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )

        return card

    def create_heading(self, number, title_text):

        widget = QWidget()
        layout = QHBoxLayout(widget)

        layout.setContentsMargins(0, 0, 0, 0)

        number_label = QLabel(number)
        number_label.setObjectName("sectionNumber")

        title_label = QLabel(title_text)
        title_label.setObjectName("sectionTitle")

        layout.addWidget(number_label)
        layout.addWidget(title_label)
        layout.addStretch()

        return widget

    def create_output(self, placeholder, height=220):

        output = QPlainTextEdit()

        output.setReadOnly(True)
        output.setMinimumHeight(height)
        output.setPlaceholderText(placeholder)

        return output

    def add_section(self, number, title, description=None):

        card = self.create_card()

        layout = QVBoxLayout(card)

        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        layout.addWidget(
            self.create_heading(number, title)
        )

        if description:

            label = QLabel(description)
            label.setObjectName("subtitle")
            label.setWordWrap(True)

            layout.addWidget(label)

        self.main_layout.addWidget(card)

        return card, layout

    # --------------------------------------------------
    # BUILD GUI
    # --------------------------------------------------

    def build_interface(self):

        header = QVBoxLayout()

        title = QLabel("PurifData")
        title.setObjectName("mainTitle")

        subtitle = QLabel(
            "AI-Driven Data Cleaning and Quality Assessment"
        )

        subtitle.setObjectName("subtitle")

        header.addWidget(title)
        header.addWidget(subtitle)

        self.main_layout.addLayout(header)

        # 01 Dataset Selection

        card, layout = self.add_section(
            "01",
            "Dataset Selection",
            "Select a CSV or Excel dataset for processing."
        )

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Select dataset...")

        browse = QPushButton("Browse Dataset")
        browse.clicked.connect(self.select_file)

        layout.addWidget(self.file_path)
        layout.addWidget(browse)

        # 02 Security

        card, layout = self.add_section(
            "02",
            "Security & File Validation",
            "Supported formats: CSV, XLSX and XLS. "
            "Maximum file size: 50 MB."
        )

        self.status = QLabel(
            "Waiting for file selection..."
        )

        self.status.setWordWrap(True)

        layout.addWidget(self.status)

        # 03 Profiling

        card, layout = self.add_section(
            "03",
            "Dataset Profiling"
        )

        button = QPushButton("Profile Dataset")
        button.clicked.connect(self.profile_dataset)

        self.profile_output = self.create_output(
            "Dataset profiling results..."
        )

        layout.addWidget(button)
        layout.addWidget(self.profile_output)

        # 04 Quality Assessment

        card, layout = self.add_section(
            "04",
            "Data Quality Assessment"
        )

        button = QPushButton("Check Data Quality")
        button.clicked.connect(self.check_data_quality)

        self.quality_output = self.create_output(
            "Quality assessment results...",
            280
        )

        layout.addWidget(button)
        layout.addWidget(self.quality_output)

        # 05 AI Analysis

        card, layout = self.add_section(
            "05",
            "AI Data Quality Analysis",
            "Gemini receives issue metadata, not original dataset records."
        )

        self.ai_btn = QPushButton("Generate AI Analysis")
        self.ai_btn.clicked.connect(self.start_ai_analysis)

        self.ai_output = self.create_output(
            "Gemini analysis results...",
            300
        )

        layout.addWidget(self.ai_btn)
        layout.addWidget(self.ai_output)

        # 06 Cleaning Plan

        card, layout = self.add_section(
            "06",
            "Intelligent Cleaning Plan"
        )

        button = QPushButton("Generate Cleaning Plan")
        button.clicked.connect(self.create_cleaning_plan)

        self.plan_output = self.create_output(
            "Proposed cleaning actions...",
            280
        )

        layout.addWidget(button)
        layout.addWidget(self.plan_output)

        # 07 Manual Correction and Approval

        card, layout = self.add_section(
            "07",
            "Manual Correction & User Approval",
            "Enter the corrections yourself. Review the preview and "
            "approve the changes before execution."
        )

        self.approval_status_label = QLabel(
            "Complete quality assessment before editing."
        )

        self.approval_status_label.setWordWrap(True)

        self.open_correction_btn = QPushButton(
            "Open Manual Correction Editor"
        )

        self.open_correction_btn.clicked.connect(
            self.open_correction_editor
        )

        self.approve_corrections_btn = QPushButton(
            "Approve Corrections"
        )

        self.approve_corrections_btn.clicked.connect(
            self.approve_manual_corrections
        )

        self.approve_corrections_btn.setEnabled(False)

        layout.addWidget(self.approval_status_label)
        layout.addWidget(self.open_correction_btn)
        layout.addWidget(self.approve_corrections_btn)

        # 08 Cleaning Preview

        card, layout = self.add_section(
            "08",
            "Cleaning Preview",
            "Review the exact changes before approving them."
        )

        button = QPushButton("Generate Cleaning Preview")
        button.clicked.connect(self.show_cleaning_preview)

        self.preview_output = self.create_output(
            "Cleaning preview...",
            250
        )

        layout.addWidget(button)
        layout.addWidget(self.preview_output)

        # 09 Execute Cleaning

        card, layout = self.add_section(
            "09",
            "Execute Approved Cleaning",
            "Only manually entered and explicitly approved corrections "
            "will be applied. The original dataset remains unchanged."
        )

        self.execute_btn = QPushButton(
            "Execute Approved Cleaning"
        )

        self.execute_btn.clicked.connect(
            self.execute_cleaning
        )

        self.execute_btn.setEnabled(False)

        self.execution_output = self.create_output(
            "Cleaning execution results...",
            220
        )

        layout.addWidget(self.execute_btn)
        layout.addWidget(self.execution_output)

        # 10 Comparison

        card, layout = self.add_section(
            "10",
            "Post-Cleaning Validation & Comparison"
        )

        button = QPushButton("Validate and Compare")
        button.clicked.connect(self.validate_and_compare)

        self.comparison_output = self.create_output(
            "Before and after comparison...",
            220
        )

        layout.addWidget(button)
        layout.addWidget(self.comparison_output)

        # 11 Final Graphical Report

        card, layout = self.add_section(
            "11",
            "Final Graphical Quality Report & Export",
            "Generate a four-page PDF containing data quality graphs."
        )

        generate_button = QPushButton(
            "Generate Graphical Report"
        )

        generate_button.clicked.connect(
            self.generate_final_report
        )

        self.export_report_btn = QPushButton(
            "Export Graphical Report as PDF"
        )

        self.export_report_btn.clicked.connect(
            self.export_final_report
        )

        self.export_report_btn.setEnabled(False)

        self.report_output = self.create_output(
            "Graphical report information...",
            180
        )

        layout.addWidget(generate_button)
        layout.addWidget(self.export_report_btn)
        layout.addWidget(self.report_output)

        # 12 Session Completion

        card, layout = self.add_section(
            "12",
            "Session Completion"
        )

        self.complete_btn = QPushButton(
            "Complete Processing Session"
        )

        self.complete_btn.clicked.connect(
            self.finish_session
        )

        self.session_output = QLabel(
            "Session will be completed after report generation."
        )

        self.session_output.setWordWrap(True)

        layout.addWidget(self.complete_btn)
        layout.addWidget(self.session_output)

        footer = QLabel(
            "PurifData | Intelligent Dataset Quality Platform"
        )

        footer.setObjectName("subtitle")
        footer.setAlignment(Qt.AlignCenter)

        self.main_layout.addWidget(footer)
        self.main_layout.addStretch()

    # --------------------------------------------------
    # RESET REPORT DATA
    # --------------------------------------------------

    def clear_report_data(self):

        self.final_report_path = None
        self.final_report_content = None
        self.final_report_data = None

        if hasattr(self, "export_report_btn"):

            self.export_report_btn.setEnabled(False)

        if hasattr(self, "report_output"):

            self.report_output.clear()

    # --------------------------------------------------
    # RESET MANUAL CORRECTIONS
    # --------------------------------------------------

    def clear_manual_corrections(self):

        self.manual_corrections = {
            "missing_changes": [],
            "duplicate_rows": [],
            "inconsistency_changes": []
        }

        self.manual_corrections_approved = False
        self.preview_generated = False

        self.approval_status_label.setText(
            "No manual corrections have been prepared."
        )

        self.approve_corrections_btn.setEnabled(False)
        self.execute_btn.setEnabled(False)

    def get_correction_counts(self):

        return {
            "missing": len(
                self.manual_corrections.get(
                    "missing_changes", []
                )
            ),

            "duplicates": len(
                self.manual_corrections.get(
                    "duplicate_rows", []
                )
            ),

            "inconsistencies": len(
                self.manual_corrections.get(
                    "inconsistency_changes", []
                )
            )
        }

    def get_total_corrections(self):

        counts = self.get_correction_counts()

        return sum(counts.values())

    # --------------------------------------------------
    # DATASET READING AND VALIDATION
    # --------------------------------------------------

    def read_dataset(self, file_name):

        return read_original_dataset(file_name)

    def is_valid_dataset(self):

        file_name = self.file_path.text()

        return (
            bool(file_name)
            and os.path.isfile(file_name)
            and "validation successful" in self.status.text().lower()
        )

    def select_file(self):

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Dataset",
            "",
            "Dataset Files (*.csv *.xlsx *.xls)"
        )

        if not file_name:
            return

        if self.current_session_id:

            try:

                complete_session(
                    self.current_session_id,
                    status="Replaced"
                )

            except Exception as error:

                print("Previous session update failed:", error)

        self.current_session_id = None

        self.file_path.setText(file_name)

        self.issue_summary = []
        self.dataset_profile = {}
        self.cleaning_plan = []

        self.assessment_completed = False

        self.cleaning_result = None
        self.comparison_result = None

        self.clear_report_data()
        self.clear_manual_corrections()

        self.complete_btn.setEnabled(True)

        for output in [
            self.profile_output,
            self.quality_output,
            self.ai_output,
            self.plan_output,
            self.preview_output,
            self.execution_output,
            self.comparison_output
        ]:

            output.clear()

        self.validate_file(file_name)

    def validate_file(self, file_name):

        extension = Path(file_name).suffix.lower()

        if not os.path.isfile(file_name):

            self.status.setText("File does not exist.")
            return

        if extension not in [".csv", ".xlsx", ".xls"]:

            self.status.setText("Unsupported file type.")
            return

        if os.path.getsize(file_name) > 50 * 1024 * 1024:

            self.status.setText(
                "File exceeds the 50 MB limit."
            )

            return

        try:

            if extension == ".csv":

                pd.read_csv(file_name, nrows=5)

            else:

                pd.read_excel(file_name, nrows=5)

            self.current_session_id = create_session(
                file_name,
                os.path.getsize(file_name)
            )

            self.status.setText(
                "File validation successful. Ready for processing."
            )

            log_event(
                self.current_session_id,
                "FILE_VALIDATION_SUCCESS",
                {
                    "extension": extension,
                    "size_bytes": os.path.getsize(file_name)
                }
            )

        except Exception as error:

            self.status.setText(
                f"File validation failed: {error}"
            )

    # --------------------------------------------------
    # DATASET PROFILING
    # --------------------------------------------------

    def profile_dataset(self):

        if not self.is_valid_dataset():

            self.profile_output.setPlainText(
                "Please select a valid dataset first."
            )

            return

        try:

            df = self.read_dataset(
                self.file_path.text()
            )

            duplicate_rows = int(
                df.duplicated().sum()
            )

            self.dataset_profile = {
                "total_rows": int(len(df)),
                "total_columns": int(len(df.columns)),
                "duplicate_rows": duplicate_rows
            }

            result = "DATASET PROFILING RESULTS\n"
            result += "=" * 45 + "\n\n"

            result += f"Total Rows: {len(df)}\n"
            result += f"Total Columns: {len(df.columns)}\n"
            result += f"Duplicate Rows: {duplicate_rows}\n"

            result += "\nCOLUMN DETAILS\n"
            result += "=" * 45 + "\n"

            for column in df.columns:

                result += f"\nColumn: {column}\n"
                result += f"Data Type: {df[column].dtype}\n"

                result += (
                    f"Missing Values: "
                    f"{int(df[column].isna().sum())}\n"
                )

            self.profile_output.setPlainText(result)

            update_session(
                self.current_session_id,
                status="Profiled",
                total_rows=len(df),
                total_columns=len(df.columns),
                duplicate_rows=duplicate_rows
            )

            log_event(
                self.current_session_id,
                "DATASET_PROFILED",
                self.dataset_profile
            )

        except Exception as error:

            self.profile_output.setPlainText(
                f"Profiling failed: {error}"
            )

    # --------------------------------------------------
    # QUALITY ASSESSMENT
    # --------------------------------------------------

    def check_data_quality(self):

        if not self.is_valid_dataset():

            self.quality_output.setPlainText(
                "Please select a valid dataset first."
            )

            return

        try:

            df = self.read_dataset(
                self.file_path.text()
            )

            issues = []
            self.issue_summary = []

            def add_issue(name, rows):

                rows = list(rows)

                if not rows:
                    return

                match = re.search(r"'([^']+)'", name)

                column = (
                    match.group(1)
                    if match
                    else "Multiple columns"
                )

                count = len(rows)

                issues.append(
                    f"{name}: {count}\n"
                    f"Excel rows: {rows[:15]}"
                )

                self.issue_summary.append({
                    "issue_name": name,
                    "column": column,
                    "count": count
                })

            # Missing values

            for column in df.columns:

                rows = (
                    df.index[df[column].isna()] + 2
                )

                add_issue(
                    f"Missing values in '{column}'",
                    rows
                )

            # Blank values

            for column in df.select_dtypes(
                include=["object", "str"]
            ).columns:

                rows = df.index[
                    df[column].apply(
                        lambda value:
                        isinstance(value, str)
                        and value.strip() == ""
                    )
                ] + 2

                add_issue(
                    f"Blank values in '{column}'",
                    rows
                )

            # Duplicate rows

            rows = df.index[
                df.duplicated(keep="first")
            ] + 2

            add_issue(
                "Duplicate records",
                rows
            )

            # Invalid Email

            if "Email" in df.columns:

                pattern = (
                    r"^[A-Za-z0-9._%+-]+@"
                    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
                )

                rows = df.index[
                    df["Email"].notna()
                    & ~df["Email"].astype(str).str.match(pattern)
                ] + 2

                add_issue(
                    "Invalid email addresses in 'Email'",
                    rows
                )

            # Invalid Phone

            if "Phone" in df.columns:

                rows = []

                for index, value in df["Phone"].items():

                    if pd.isna(value):
                        continue

                    digits = re.sub(
                        r"\D",
                        "",
                        str(value)
                    )

                    if len(digits) != 10:
                        rows.append(index + 2)

                add_issue(
                    "Invalid phone numbers in 'Phone'",
                    rows
                )

            # Invalid Age

            if "Age" in df.columns:

                values = pd.to_numeric(
                    df["Age"],
                    errors="coerce"
                )

                rows = df.index[
                    df["Age"].notna()
                    & (
                        values.isna()
                        | (values < 0)
                        | (values > 100)
                    )
                ] + 2

                add_issue(
                    "Invalid age values in 'Age'",
                    rows
                )

            # Invalid Salary

            if "Salary" in df.columns:

                values = pd.to_numeric(
                    df["Salary"].astype(str).str.replace(
                        ",", "", regex=False
                    ),
                    errors="coerce"
                )

                rows = df.index[
                    df["Salary"].notna()
                    & (values.isna() | (values < 0))
                ] + 2

                add_issue(
                    "Invalid salary values in 'Salary'",
                    rows
                )

                rows = df.index[
                    values == 0
                ] + 2

                add_issue(
                    "Suspicious zero salary in 'Salary'",
                    rows
                )

            # Invalid Joining Date

            if "Joining_Date" in df.columns:

                values = pd.to_datetime(
                    df["Joining_Date"],
                    errors="coerce",
                    format="mixed"
                )

                rows = df.index[
                    df["Joining_Date"].notna()
                    & values.isna()
                ] + 2

                add_issue(
                    "Invalid joining dates in 'Joining_Date'",
                    rows
                )

            # Gender

            if "Gender" in df.columns:

                valid = [
                    "male",
                    "female",
                    "other",
                    "m",
                    "f"
                ]

                rows = df.index[
                    df["Gender"].notna()
                    & ~df["Gender"].astype(str).str.strip().str.lower().isin(valid)
                ] + 2

                add_issue(
                    "Unrecognized gender values in 'Gender'",
                    rows
                )

            # Status

            if "Status" in df.columns:

                valid = [
                    "active",
                    "inactive",
                    "on leave"
                ]

                rows = df.index[
                    df["Status"].notna()
                    & ~df["Status"].astype(str).str.strip().str.lower().isin(valid)
                ] + 2

                add_issue(
                    "Unrecognized status values in 'Status'",
                    rows
                )

            # Text capitalization inconsistencies

            for column in df.select_dtypes(
                include=["object", "str"]
            ).columns:

                groups = {}

                for index, value in df[column].items():

                    if isinstance(value, str) and value.strip():

                        key = value.strip().casefold()

                        groups.setdefault(key, [])

                        if value.strip() not in groups[key]:
                            groups[key].append(value.strip())

                inconsistent_rows = []

                for spellings in groups.values():

                    if len(spellings) > 1:

                        for index, value in df[column].items():

                            if (
                                isinstance(value, str)
                                and value.strip() in spellings
                            ):

                                inconsistent_rows.append(
                                    index + 2
                                )

                if inconsistent_rows:

                    add_issue(
                        f"Inconsistent text capitalization in '{column}'",
                        sorted(set(inconsistent_rows))
                    )

            self.dataset_profile = {
                "total_rows": int(len(df)),
                "total_columns": int(len(df.columns)),
                "duplicate_rows": int(df.duplicated().sum())
            }

            result = "DATA QUALITY ASSESSMENT RESULTS\n"
            result += "=" * 45 + "\n\n"

            result += f"Rows checked: {len(df)}\n"
            result += f"Columns checked: {len(df.columns)}\n"
            result += f"Issue categories: {len(issues)}\n\n"

            for number, issue in enumerate(issues, 1):

                result += f"{number}. {issue}\n\n"

            if not issues:

                result += "No quality issues detected.\n"

            self.quality_output.setPlainText(result)

            # Reset previous workflow results

            self.ai_output.clear()
            self.plan_output.clear()
            self.preview_output.clear()
            self.execution_output.clear()
            self.comparison_output.clear()

            self.cleaning_plan = []

            self.cleaning_result = None
            self.comparison_result = None

            self.clear_report_data()

            self.assessment_completed = True

            self.clear_manual_corrections()

            update_session(
                self.current_session_id,
                status="Quality Assessed",
                total_rows=len(df),
                total_columns=len(df.columns),
                duplicate_rows=int(df.duplicated().sum()),
                issue_categories=len(issues)
            )

            log_event(
                self.current_session_id,
                "QUALITY_ASSESSMENT_COMPLETED",
                {
                    "issue_categories": len(issues),
                    "issues": self.issue_summary
                }
            )

        except Exception as error:

            self.assessment_completed = False

            self.quality_output.setPlainText(
                f"Quality assessment failed: {error}"
            )

    # --------------------------------------------------
    # GEMINI AI ANALYSIS
    # --------------------------------------------------

    

    # --------------------------------------------------
    # GEMINI AI ANALYSIS
    # --------------------------------------------------

    def start_ai_analysis(self):

        if not self.is_valid_dataset():

            self.ai_output.setPlainText(
                "Please select a valid dataset."
            )
            return

        if not self.assessment_completed:

            self.ai_output.setPlainText(
                "Complete quality assessment first."
            )
            return

        if not self.current_session_id:

            self.ai_output.setPlainText(
                "No active database session."
            )
            return

        if self.ai_worker and self.ai_worker.isRunning():
            return

        # Check whether Gemini API key exists
        api_key = get_api_key()

        if not api_key:

            dialog = QInputDialog(self)

            dialog.setWindowTitle(
                "Gemini API Configuration"
            )

            dialog.setLabelText(
                "Paste your Gemini API key:\n\n"
                "Get your API key from Google AI Studio."
            )

            # Visible input field supports Ctrl + V
            dialog.setTextEchoMode(QLineEdit.Normal)

            dialog.setOkButtonText("Save API Key")
            dialog.setCancelButtonText("Cancel")

            if not dialog.exec():
                return

            api_key = dialog.textValue().strip()

            if not api_key:

                QMessageBox.warning(
                    self,
                    "API Key Required",
                    "Please enter your Gemini API key."
                )
                return

            # Save API key locally
            if not save_api_key(api_key):

                QMessageBox.critical(
                    self,
                    "Configuration Error",
                    "Could not save the API key locally."
                )
                return

            QMessageBox.information(
                self,
                "Configuration Successful",
                "Gemini API key saved successfully.\n\n"
                "You can now generate AI analysis."
            )

        # Start Gemini analysis
        self.ai_btn.setEnabled(False)
        self.ai_btn.setText("Analyzing...")

        self.ai_output.setPlainText(
            "Gemini is analyzing the issue metadata. Please wait..."
        )

        self.ai_worker = AIAnalysisWorker(
            self.issue_summary.copy(),
            self.dataset_profile.copy()
        )

        self.ai_worker.finished_signal.connect(
            self.display_ai_analysis
        )

        self.ai_worker.start()

    # --------------------------------------------------
    # DISPLAY AI ANALYSIS
    # --------------------------------------------------

    def display_ai_analysis(self, result):

        self.ai_output.setPlainText(result)

        failed = (
            result.startswith("Error:")
            or "Gemini analysis failed:" in result
            or "quota exceeded" in result.lower()
        )

        try:

            log_event(
                self.current_session_id,
                "AI_ANALYSIS_FAILED" if failed
                else "AI_ANALYSIS_COMPLETED",
                {
                    "result_characters": len(result)
                }
            )

            if not failed:

                report_path = (
                    Path(__file__).resolve().parent
                    / "ai_analysis_result.txt"
                )

                if report_path.exists():

                    save_report(
                        self.current_session_id,
                        "AI Analysis",
                        str(report_path)
                    )

                update_session(
                    self.current_session_id,
                    status="AI Analysis Completed"
                )

        except Exception as error:

            print("AI logging failed:", error)

        finally:

            self.ai_btn.setEnabled(True)
            self.ai_btn.setText("Generate AI Analysis")

    # --------------------------------------------------
    # CLEANING PLAN
    # --------------------------------------------------

    def create_cleaning_plan(self):

        if not self.assessment_completed:

            self.plan_output.setPlainText(
                "Complete quality assessment first."
            )

            return

        if not self.issue_summary:

            self.plan_output.setPlainText(
                "No issues detected. No cleaning plan is required."
            )

            self.cleaning_plan = []

            return

        try:

            self.cleaning_plan = generate_cleaning_plan(
                self.issue_summary
            )

            result = "PROPOSED CLEANING PLAN\n"
            result += "=" * 45 + "\n\n"

            for number, item in enumerate(
                self.cleaning_plan,
                1
            ):

                result += (
                    f"{number}. {item.get('issue_name', 'Unknown issue')}\n"
                    f"Column: {item.get('column', '')}\n"
                    f"Count: {item.get('count', 0)}\n"
                    f"Priority: {item.get('priority', 'Normal')}\n"
                    f"Recommended Action: {item.get('action', 'Manual review')}\n\n"
                )

            result += (
                "AI recommendations are advisory. "
                "You will enter and approve the actual corrections manually."
            )

            self.plan_output.setPlainText(result)

            log_event(
                self.current_session_id,
                "CLEANING_PLAN_GENERATED",
                {
                    "total_actions": len(self.cleaning_plan)
                }
            )

            update_session(
                self.current_session_id,
                status="Cleaning Plan Generated"
            )

        except Exception as error:

            self.plan_output.setPlainText(
                f"Cleaning plan generation failed: {error}"
            )

    # --------------------------------------------------
    # OPEN MANUAL CORRECTION EDITOR
    # --------------------------------------------------

    def open_correction_editor(self):

        if not self.is_valid_dataset():

            QMessageBox.warning(
                self,
                "Dataset Required",
                "Select a valid dataset first."
            )

            return

        if not self.assessment_completed:

            QMessageBox.warning(
                self,
                "Assessment Required",
                "Complete data quality assessment first."
            )

            return

        try:

            df = read_original_dataset(
                self.file_path.text()
            )

            dialog = ManualCorrectionDialog(
                df,
                self
            )

            if dialog.exec():

                corrections = dialog.get_corrections()

                self.manual_corrections = corrections

                self.manual_corrections_approved = False
                self.preview_generated = False

                self.cleaning_result = None
                self.comparison_result = None

                self.clear_report_data()

                self.preview_output.clear()
                self.execution_output.clear()
                self.comparison_output.clear()

                self.execute_btn.setEnabled(False)
                self.approve_corrections_btn.setEnabled(False)

                counts = self.get_correction_counts()

                total = sum(counts.values())

                self.approval_status_label.setText(
                    f"Corrections prepared: {total}\n"
                    f"Missing values: {counts['missing']} | "
                    f"Duplicates: {counts['duplicates']} | "
                    f"Inconsistencies: {counts['inconsistencies']}\n\n"
                    "Generate the preview before approving."
                )

                log_event(
                    self.current_session_id,
                    "MANUAL_CORRECTIONS_PREPARED",
                    {
                        "missing_changes": counts["missing"],
                        "duplicate_rows": counts["duplicates"],
                        "inconsistency_changes": counts["inconsistencies"]
                    }
                )

                QMessageBox.information(
                    self,
                    "Corrections Prepared",
                    f"{total} proposed corrections prepared.\n\n"
                    "No changes have been applied to the original dataset.\n\n"
                    "Generate the preview to continue."
                )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Correction Editor Error",
                str(error)
            )

    # --------------------------------------------------
    # CLEANING PREVIEW
    # --------------------------------------------------

    def show_cleaning_preview(self):

        if not self.is_valid_dataset():

            self.preview_output.setPlainText(
                "Select a valid dataset first."
            )

            return

        if not self.assessment_completed:

            self.preview_output.setPlainText(
                "Complete quality assessment first."
            )

            return

        if self.get_total_corrections() == 0:

            self.preview_output.setPlainText(
                "No manual corrections have been prepared.\n"
                "Open the Manual Correction Editor first."
            )

            return

        try:

            preview = generate_cleaning_preview(
                self.file_path.text(),
                self.cleaning_plan,
                self.manual_corrections
            )

            result = "MANUAL CLEANING PREVIEW\n"
            result += "=" * 50 + "\n\n"

            for item in preview:

                result += (
                    f"Operation: {item['operation']}\n"
                    f"Description: {item['description']}\n"
                    f"Affected: {item['affected']}\n"
                    f"Status: {item['status']}\n"
                    f"Details:\n{item['details']}\n\n"
                )

            self.preview_output.setPlainText(result)

            self.preview_generated = True

            self.manual_corrections_approved = False

            self.execute_btn.setEnabled(False)

            self.approve_corrections_btn.setEnabled(
                self.get_total_corrections() > 0
            )

            self.approval_status_label.setText(
                "Preview generated. Review the proposed changes "
                "and click Approve Corrections to continue."
            )

            log_event(
                self.current_session_id,
                "MANUAL_CLEANING_PREVIEW_GENERATED",
                {
                    "preview_items": len(preview),
                    "proposed_changes": self.get_total_corrections()
                }
            )

        except Exception as error:

            self.preview_generated = False

            self.approve_corrections_btn.setEnabled(False)

            self.preview_output.setPlainText(
                f"Preview failed: {error}"
            )

    # --------------------------------------------------
    # APPROVE MANUAL CORRECTIONS
    # --------------------------------------------------

    def approve_manual_corrections(self):

        if not self.preview_generated:

            QMessageBox.warning(
                self,
                "Preview Required",
                "Generate and review the cleaning preview first."
            )

            return

        total = self.get_total_corrections()

        if total == 0:

            QMessageBox.warning(
                self,
                "No Corrections",
                "There are no proposed corrections to approve."
            )

            return

        counts = self.get_correction_counts()

        answer = QMessageBox.question(
            self,
            "Approve Manual Corrections",

            "Do you approve the following proposed changes?\n\n"
            f"Missing values to fill: {counts['missing']}\n"
            f"Duplicate rows to delete: {counts['duplicates']}\n"
            f"Inconsistencies to update: {counts['inconsistencies']}\n\n"
            "The original dataset will not be overwritten.",

            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        self.manual_corrections_approved = True

        self.execute_btn.setEnabled(True)

        self.approval_status_label.setText(
            f"Corrections approved successfully.\n"
            f"Total approved changes: {total}\n"
            "You can now execute the cleaning process."
        )

        self.approve_corrections_btn.setEnabled(False)

        try:

            log_event(
                self.current_session_id,
                "MANUAL_CORRECTIONS_APPROVED",
                {
                    "missing_changes": counts["missing"],
                    "duplicate_rows": counts["duplicates"],
                    "inconsistency_changes": counts["inconsistencies"],
                    "total_changes": total
                }
            )

            update_session(
                self.current_session_id,
                status="Manual Corrections Approved"
            )

        except Exception as error:

            print("Approval logging failed:", error)

        QMessageBox.information(
            self,
            "Approval Successful",
            "Manual corrections approved.\n\n"
            "You can now execute the cleaning process."
        )

    # --------------------------------------------------
    # EXECUTE APPROVED CLEANING
    # --------------------------------------------------

    def execute_cleaning(self):

        if not self.is_valid_dataset():

            QMessageBox.warning(
                self,
                "Dataset Required",
                "Select a valid dataset first."
            )

            return

        if not self.manual_corrections_approved:

            QMessageBox.warning(
                self,
                "Approval Required",
                "Approve the manual corrections before execution."
            )

            return

        if not self.preview_generated:

            QMessageBox.warning(
                self,
                "Preview Required",
                "Generate the cleaning preview first."
            )

            return

        if self.get_total_corrections() == 0:

            QMessageBox.warning(
                self,
                "No Corrections",
                "No manual corrections are available."
            )

            return

        answer = QMessageBox.question(
            self,
            "Confirm Cleaning",

            "Execute the approved manual corrections?\n\n"
            "A separate cleaned dataset will be created.\n"
            "Your original dataset will remain unchanged.",

            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        try:

            self.execute_btn.setEnabled(False)

            self.execution_output.setPlainText(
                "Applying approved manual corrections..."
            )

            self.cleaning_result = clean_dataset(
                self.file_path.text(),
                corrections=self.manual_corrections
            )

            result = "MANUAL CLEANING EXECUTION SUMMARY\n"
            result += "=" * 50 + "\n\n"

            result += (
                f"Original rows: "
                f"{self.cleaning_result['original_rows']}\n"

                f"Cleaned rows: "
                f"{self.cleaning_result['cleaned_rows']}\n"

                f"Rows removed: "
                f"{self.cleaning_result['rows_removed']}\n"

                f"Total operations: "
                f"{self.cleaning_result.get('total_operations', 0)}\n"

                f"Output file: "
                f"{self.cleaning_result['cleaned_file']}\n\n"
            )

            for item in self.cleaning_result["results"]:

                result += (
                    f"Operation: {item['operation']}\n"
                    f"Status: {item['status']}\n"
                    f"Affected: {item.get('affected', 0)}\n"
                    f"Details: "
                    f"{item.get('details', item.get('reason', ''))}\n\n"
                )

            result += (
                "\nOriginal dataset has not been overwritten."
            )

            self.execution_output.setPlainText(result)

            self.comparison_result = None

            self.clear_report_data()
            self.comparison_output.clear()

            counts = self.get_correction_counts()

            log_event(
                self.current_session_id,
                "MANUAL_CLEANING_EXECUTED",
                {
                    "original_file": self.cleaning_result["original_file"],
                    "cleaned_file": self.cleaning_result["cleaned_file"],
                    "missing_changes": counts["missing"],
                    "duplicate_rows": counts["duplicates"],
                    "inconsistency_changes": counts["inconsistencies"],
                    "rows_removed": self.cleaning_result["rows_removed"]
                }
            )

            update_session(
                self.current_session_id,
                status="Cleaning Executed"
            )

            QMessageBox.information(
                self,
                "Cleaning Completed",
                "Approved corrections have been applied successfully.\n\n"
                f"Cleaned dataset:\n"
                f"{self.cleaning_result['cleaned_file']}"
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Cleaning Failed",
                str(error)
            )

            self.execution_output.setPlainText(
                f"Cleaning failed: {error}"
            )

        finally:

            self.execute_btn.setEnabled(
                self.manual_corrections_approved
            )

    # --------------------------------------------------
    # POST-CLEANING VALIDATION AND COMPARISON
    # --------------------------------------------------

    def validate_and_compare(self):

        if not self.cleaning_result:

            self.comparison_output.setPlainText(
                "Execute cleaning first."
            )

            return

        try:

            original = read_original_dataset(
                self.cleaning_result["original_file"]
            )

            cleaned = read_original_dataset(
                self.cleaning_result["cleaned_file"]
            )

            original_missing = int(
                original.isna().sum().sum()
            )

            cleaned_missing = int(
                cleaned.isna().sum().sum()
            )

            original_duplicates = int(
                original.duplicated().sum()
            )

            cleaned_duplicates = int(
                cleaned.duplicated().sum()
            )

            same_columns = (
                list(original.columns) == list(cleaned.columns)
            )

            self.comparison_result = {

                "original_rows": len(original),
                "cleaned_rows": len(cleaned),

                "original_columns": len(original.columns),
                "cleaned_columns": len(cleaned.columns),

                "original_missing": original_missing,
                "cleaned_missing": cleaned_missing,

                "original_duplicates": original_duplicates,
                "cleaned_duplicates": cleaned_duplicates,

                "columns_unchanged": same_columns,

                "validation_passed": same_columns
            }

            result = "BEFORE AND AFTER COMPARISON\n"
            result += "=" * 45 + "\n\n"

            result += (
                f"Original rows: {len(original)}\n"
                f"Cleaned rows: {len(cleaned)}\n"

                f"Original columns: {len(original.columns)}\n"
                f"Cleaned columns: {len(cleaned.columns)}\n\n"

                f"Original missing values: {original_missing}\n"
                f"Cleaned missing values: {cleaned_missing}\n"

                f"Original duplicate rows: {original_duplicates}\n"
                f"Cleaned duplicate rows: {cleaned_duplicates}\n\n"

                f"Column structure unchanged: "
                f"{'Yes' if same_columns else 'No'}\n"

                f"Validation: "
                f"{'PASSED' if same_columns else 'FAILED'}\n"
            )

            self.comparison_output.setPlainText(result)

            self.clear_report_data()

            log_event(
                self.current_session_id,
                "POST_CLEANING_VALIDATION",
                self.comparison_result
            )

            update_session(
                self.current_session_id,
                status="Post-Cleaning Validation Completed"
            )

        except Exception as error:

            self.comparison_output.setPlainText(
                f"Validation failed: {error}"
            )

    # --------------------------------------------------
    # CALCULATE DATA QUALITY METRICS
    # --------------------------------------------------

    def calculate_report_metrics(self, df):

        rows = len(df)
        columns = len(df.columns)

        # Missing and blank values

        missing_mask = df.isna().copy()

        for column in df.columns:

            if pd.api.types.is_object_dtype(df[column]):

                blank_mask = df[column].apply(
                    lambda value:
                    isinstance(value, str)
                    and value.strip() == ""
                )

                missing_mask[column] = (
                    missing_mask[column] | blank_mask
                )

        # Text inconsistencies

        inconsistency_mask = pd.DataFrame(
            False,
            index=range(rows),
            columns=range(columns)
        )

        for column_index, column in enumerate(df.columns):

            if not pd.api.types.is_object_dtype(df[column]):
                continue

            groups = {}

            for row_index in range(rows):

                value = df.iloc[row_index, column_index]

                if isinstance(value, str) and value.strip():

                    key = value.strip().casefold()

                    groups.setdefault(key, set())
                    groups[key].add(value.strip())

            for row_index in range(rows):

                value = df.iloc[row_index, column_index]

                if not isinstance(value, str) or not value.strip():
                    continue

                key = value.strip().casefold()

                if len(groups.get(key, set())) > 1:

                    inconsistency_mask.iat[
                        row_index, column_index
                    ] = True

        # Duplicate rows

        duplicate_mask = df.duplicated(
            keep="first"
        ).to_numpy()

        # Combine problematic cells

        problematic_mask = (
            missing_mask.to_numpy(dtype=bool)
            | inconsistency_mask.to_numpy(dtype=bool)
        )

        # Mark all cells in duplicate rows as problematic

        if columns > 0 and len(duplicate_mask) > 0:

            problematic_mask[duplicate_mask, :] = True

        total_cells = rows * columns

        problematic_cells = int(
            problematic_mask.sum()
        )

        valid_cells = max(
            0,
            total_cells - problematic_cells
        )

        if total_cells > 0:

            quality_score = (
                valid_cells / total_cells
            ) * 100

        else:

            quality_score = 0

        return {

            "rows": rows,
            "columns": columns,

            "missing_values": int(
                missing_mask.to_numpy().sum()
            ),

            "duplicate_rows": int(
                duplicate_mask.sum()
            ),

            "inconsistent_values": int(
                inconsistency_mask.to_numpy().sum()
            ),

            "total_cells": total_cells,
            "valid_cells": valid_cells,
            "problematic_cells": problematic_cells,

            "quality_score": round(
                quality_score, 2
            )
        }

    # --------------------------------------------------
    # GENERATE GRAPHICAL QUALITY REPORT
    # --------------------------------------------------

    def generate_final_report(self):

        if not self.cleaning_result:

            self.report_output.setPlainText(
                "Execute cleaning before generating the final report."
            )

            return

        if not self.comparison_result:

            self.report_output.setPlainText(
                "Complete post-cleaning validation first."
            )

            return

        if not self.comparison_result["validation_passed"]:

            self.report_output.setPlainText(
                "Validation failed. Please review the cleaned dataset."
            )

            return

        try:

            original = read_original_dataset(
                self.cleaning_result["original_file"]
            )

            cleaned = read_original_dataset(
                self.cleaning_result["cleaned_file"]
            )

            original_metrics = self.calculate_report_metrics(
                original
            )

            cleaned_metrics = self.calculate_report_metrics(
                cleaned
            )

            counts = self.get_correction_counts()

            self.final_report_data = {

                "generated": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                "dataset": Path(
                    self.file_path.text()
                ).name,

                "original_file": Path(
                    self.cleaning_result["original_file"]
                ).name,

                "cleaned_file": Path(
                    self.cleaning_result["cleaned_file"]
                ).name,

                "original": original_metrics,
                "cleaned": cleaned_metrics,

                "issues": self.issue_summary.copy(),

                "corrections": counts,

                "cleaning_operations": self.cleaning_result.get(
                    "results", []
                )
            }

            self.final_report_path = None
            self.final_report_content = None

            self.export_report_btn.setEnabled(True)

            self.report_output.setPlainText(
                "GRAPHICAL QUALITY REPORT READY\n\n"
                "Four visualizations prepared successfully:\n\n"
                "1. Before vs After Data Quality Score\n"
                "2. Initial Detected Issues\n"
                "3. Cleaning Results Comparison\n"
                "4. Final Data Quality Distribution\n\n"
                f"Original quality score: "
                f"{original_metrics['quality_score']}%\n"
                f"Cleaned quality score: "
                f"{cleaned_metrics['quality_score']}%\n\n"
                "Click Export Graphical Report as PDF."
            )

            log_event(
                self.current_session_id,
                "GRAPHICAL_REPORT_GENERATED",
                {
                    "original_quality": original_metrics["quality_score"],
                    "cleaned_quality": cleaned_metrics["quality_score"],
                    "graphs": 4
                }
            )

            update_session(
                self.current_session_id,
                status="Final Report Generated"
            )

        except Exception as error:

            self.final_report_data = None
            self.final_report_path = None

            self.export_report_btn.setEnabled(False)

            self.report_output.setPlainText(
                f"Graphical report generation failed: {error}"
            )

    # --------------------------------------------------
    # EXPORT GRAPHICAL REPORT AS PDF
    # --------------------------------------------------

    def export_final_report(self):

        if not self.final_report_data:

            QMessageBox.warning(
                self,
                "Report Required",
                "Generate the final report first."
            )

            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Graphical Quality Report",
            "PurifData_Graphical_Report.pdf",
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        try:

            import matplotlib

            matplotlib.use("Agg")

            import matplotlib.pyplot as plt

            from matplotlib.backends.backend_pdf import PdfPages
            from textwrap import fill

            report = self.final_report_data

            original = report["original"]
            cleaned = report["cleaned"]

            with PdfPages(file_path) as pdf:

                # ------------------------------------------
                # PAGE 1: DATA QUALITY SCORE
                # ------------------------------------------

                fig, ax = plt.subplots(figsize=(11, 7))

                labels = [
                    "Before Cleaning",
                    "After Cleaning"
                ]

                scores = [
                    original["quality_score"],
                    cleaned["quality_score"]
                ]

                bars = ax.bar(
                    labels,
                    scores,
                    width=0.5
                )

                ax.set_title(
                    "PurifData - Before vs After Data Quality",
                    fontsize=18,
                    fontweight="bold",
                    pad=25
                )

                ax.set_ylabel("Data Quality Score (%)")
                ax.set_ylim(0, 110)

                ax.grid(
                    axis="y",
                    linestyle="--",
                    alpha=0.4
                )

                for bar, score in zip(bars, scores):

                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 2,
                        f"{score:.2f}%",
                        ha="center",
                        fontsize=13,
                        fontweight="bold"
                    )

                fig.text(
                    0.5,
                    0.03,
                    "Score is calculated from missing/blank cells, "
                    "duplicate rows and text inconsistencies.",
                    ha="center",
                    fontsize=9
                )

                fig.tight_layout(
                    rect=[0, 0.07, 1, 0.95]
                )

                pdf.savefig(fig)
                plt.close(fig)

                # ------------------------------------------
                # PAGE 2: DETECTED ISSUES
                # ------------------------------------------

                issues = report["issues"]

                if issues:

                    chart_height = max(
                        7,
                        min(16, len(issues) * 0.38 + 3)
                    )

                    fig, ax = plt.subplots(
                        figsize=(11, chart_height)
                    )

                    issue_names = [
                        fill(
                            item["issue_name"],
                            width=38
                        )
                        for item in issues
                    ]

                    issue_counts = [
                        item["count"]
                        for item in issues
                    ]

                    positions = list(
                        range(len(issue_names))
                    )

                    ax.barh(
                        positions,
                        issue_counts
                    )

                    ax.set_yticks(positions)
                    ax.set_yticklabels(
                        issue_names,
                        fontsize=9
                    )

                    ax.invert_yaxis()

                    ax.set_xlabel(
                        "Number of Detected Issues"
                    )

                    ax.grid(
                        axis="x",
                        linestyle="--",
                        alpha=0.4
                    )

                else:

                    fig, ax = plt.subplots(
                        figsize=(11, 7)
                    )

                    ax.text(
                        0.5,
                        0.5,
                        "No quality issues detected",
                        ha="center",
                        va="center",
                        fontsize=16,
                        transform=ax.transAxes
                    )

                    ax.set_axis_off()

                ax.set_title(
                    "Initial Dataset - Detected Issues",
                    fontsize=18,
                    fontweight="bold",
                    pad=25
                )

                fig.tight_layout()

                pdf.savefig(fig)
                plt.close(fig)

                # ------------------------------------------
                # PAGE 3: CLEANING RESULTS
                # ------------------------------------------

                fig, ax = plt.subplots(figsize=(11, 7))

                categories = [
                    "Missing Values",
                    "Duplicate Rows",
                    "Text Inconsistencies"
                ]

                before_values = [
                    original["missing_values"],
                    original["duplicate_rows"],
                    original["inconsistent_values"]
                ]

                after_values = [
                    cleaned["missing_values"],
                    cleaned["duplicate_rows"],
                    cleaned["inconsistent_values"]
                ]

                x = list(range(len(categories)))

                width = 0.35

                before_bars = ax.bar(
                    [i - width / 2 for i in x],
                    before_values,
                    width,
                    label="Before Cleaning"
                )

                after_bars = ax.bar(
                    [i + width / 2 for i in x],
                    after_values,
                    width,
                    label="After Cleaning"
                )

                ax.set_title(
                    "Cleaning Results - Before vs After",
                    fontsize=18,
                    fontweight="bold",
                    pad=25
                )

                ax.set_ylabel("Number of Issues")

                ax.set_xticks(x)
                ax.set_xticklabels(categories)

                ax.legend()

                ax.grid(
                    axis="y",
                    linestyle="--",
                    alpha=0.4
                )

                for bars in [before_bars, after_bars]:

                    for bar in bars:

                        ax.annotate(
                            str(int(bar.get_height())),
                            (
                                bar.get_x() + bar.get_width() / 2,
                                bar.get_height()
                            ),
                            xytext=(0, 4),
                            textcoords="offset points",
                            ha="center",
                            fontsize=9
                        )

                fig.tight_layout()

                pdf.savefig(fig)
                plt.close(fig)

                # ------------------------------------------
                # PAGE 4: DATA QUALITY DISTRIBUTION
                # ------------------------------------------

                fig, ax = plt.subplots(figsize=(11, 7))

                valid = cleaned["valid_cells"]

                problematic = cleaned["problematic_cells"]

                if cleaned["total_cells"] > 0:

                    values = [
                        valid,
                        problematic
                    ]

                    labels = [
                        f"Valid Cells\n{valid:,}",
                        f"Problematic Cells\n{problematic:,}"
                    ]

                    ax.pie(
                        values,
                        labels=labels,
                        autopct="%1.1f%%",
                        startangle=90,
                        wedgeprops={
                            "width": 0.42,
                            "edgecolor": "white"
                        },
                        textprops={
                            "fontsize": 11
                        }
                    )

                else:

                    ax.text(
                        0.5,
                        0.5,
                        "No dataset cells available",
                        ha="center",
                        va="center",
                        fontsize=15,
                        transform=ax.transAxes
                    )

                ax.set_title(
                    "Final Dataset - Data Quality Distribution",
                    fontsize=18,
                    fontweight="bold",
                    pad=25
                )

                fig.text(
                    0.5,
                    0.04,
                    f"Dataset: {report['dataset']} | "
                    f"Quality Score: {cleaned['quality_score']:.2f}%",
                    ha="center",
                    fontsize=10
                )

                fig.tight_layout(
                    rect=[0, 0.07, 1, 0.95]
                )

                pdf.savefig(fig)
                plt.close(fig)

            # ------------------------------------------
            # VERIFY PDF
            # ------------------------------------------

            if not os.path.isfile(file_path):

                raise Exception(
                    "PDF file could not be created."
                )

            if os.path.getsize(file_path) == 0:

                raise Exception(
                    "The exported PDF is empty."
                )

            self.final_report_path = file_path

            save_report(
                self.current_session_id,
                "Graphical Quality Report",
                file_path
            )

            log_event(
                self.current_session_id,
                "GRAPHICAL_REPORT_EXPORTED_AS_PDF",
                {
                    "pdf_path": file_path,
                    "graphs": 4
                }
            )

            QMessageBox.information(
                self,
                "PDF Export Successful",
                "Your graphical quality report has been exported.\n\n"
                "Graphs included: 4\n\n"
                f"Location:\n{file_path}"
            )

            self.report_output.setPlainText(
                "GRAPHICAL PDF REPORT EXPORTED SUCCESSFULLY\n\n"
                f"PDF Location:\n{file_path}\n\n"
                "Four graphs included successfully."
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "PDF Export Failed",
                str(error)
            )

    # --------------------------------------------------
    # SESSION COMPLETION
    # --------------------------------------------------

    def finish_session(self):

        if not self.current_session_id:

            QMessageBox.warning(
                self,
                "No Session",
                "There is no active processing session."
            )

            return

        if not self.final_report_path:

            QMessageBox.warning(
                self,
                "Report Required",
                "Generate and export the graphical PDF report first."
            )

            return

        try:

            log_event(
                self.current_session_id,
                "PROCESSING_WORKFLOW_COMPLETED",
                {
                    "cleaned_file": self.cleaning_result["cleaned_file"],
                    "final_report": self.final_report_path
                }
            )

            complete_session(
                self.current_session_id,
                status="Completed"
            )

            self.session_output.setText(
                "Processing session completed successfully. "
                "Audit history has been saved."
            )

            self.complete_btn.setEnabled(False)

            QMessageBox.information(
                self,
                "PurifData",
                "Your dataset processing session is complete."
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Session Error",
                str(error)
            )

    # --------------------------------------------------
    # APPLICATION CLOSE
    # --------------------------------------------------

    def closeEvent(self, event):

        if self.current_session_id:

            try:

                log_event(
                    self.current_session_id,
                    "APPLICATION_CLOSED",
                    {
                        "message": "Application closed by user."
                    }
                )

            except Exception as error:

                print("Close logging failed:", error)

        event.accept()


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = PurifDataApp()

    window.show()

    sys.exit(app.exec())