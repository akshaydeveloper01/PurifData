
import pandas as pd

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QAbstractItemView
)

from PySide6.QtCore import Qt


class ManualCorrectionDialog(QDialog):

    def __init__(self, dataframe, parent=None):

        super().__init__(parent)

        self.setWindowTitle("PurifData - Manual Data Correction")
        self.resize(1050, 650)

        self.df = dataframe.copy()

        self.missing_changes = []
        self.duplicate_rows = []
        self.inconsistency_changes = []

        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #111827;
                color: #E5E7EB;
                font-family: Segoe UI;
                font-size: 10pt;
            }

            QLabel {
                color: #E5E7EB;
            }

            QTabWidget::pane {
                border: 1px solid #374151;
                background-color: #1F2937;
            }

            QTabBar::tab {
                background-color: #1F2937;
                color: #D1D5DB;
                padding: 10px 18px;
                margin-right: 3px;
            }

            QTabBar::tab:selected {
                background-color: #2563EB;
                color: white;
            }

            QTableWidget {
                background-color: #1F2937;
                alternate-background-color: #263244;
                color: #E5E7EB;
                gridline-color: #374151;
                border: 1px solid #374151;
            }

            QHeaderView::section {
                background-color: #374151;
                color: white;
                padding: 8px;
                border: none;
            }

            QTableWidget QLineEdit {
                background-color: #111827;
                color: white;
                padding: 5px;
                border: 1px solid #4B5563;
            }

            QPushButton {
                background-color: #2563EB;
                color: white;
                padding: 9px 16px;
                border-radius: 6px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #1D4ED8;
            }

            QPushButton#cancelButton {
                background-color: #4B5563;
            }

            QPushButton#cancelButton:hover {
                background-color: #374151;
            }
        """)

        self.build_interface()

        self.load_missing_values()
        self.load_duplicates()
        self.load_inconsistencies()

    # --------------------------------------------------
    # GET PERSON NAME
    # --------------------------------------------------

    def get_person_name(self, row_index):

        if "Name" not in self.df.columns:
            return "Not available"

        value = self.df.iloc[row_index]["Name"]

        if pd.isna(value) or str(value).strip() == "":
            return "Not available"

        return str(value)

    # --------------------------------------------------
    # MAIN INTERFACE
    # --------------------------------------------------

    def build_interface(self):

        main_layout = QVBoxLayout(self)

        heading = QLabel("Manual Dataset Correction")
        heading.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        description = QLabel(
            "Review the detected problems and enter corrections "
            "before applying them to the dataset."
        )

        description.setWordWrap(True)

        main_layout.addWidget(heading)
        main_layout.addWidget(description)

        self.tabs = QTabWidget()

        main_layout.addWidget(self.tabs)

        # Missing values tab

        missing_tab = QWidget()
        missing_layout = QVBoxLayout(missing_tab)

        missing_layout.addWidget(
            QLabel(
                "Enter the correct value for each missing cell. "
                "The Name column identifies the affected record."
            )
        )

        self.missing_table = QTableWidget()

        self.missing_table.setColumnCount(5)

        self.missing_table.setHorizontalHeaderLabels([
            "Excel Row",
            "Name",
            "Column",
            "Current Value",
            "Enter Correct Value"
        ])

        self.configure_table(self.missing_table)

        missing_layout.addWidget(self.missing_table)

        self.missing_count_label = QLabel(
            "Missing values: 0"
        )

        missing_layout.addWidget(self.missing_count_label)

        self.tabs.addTab(
            missing_tab,
            "Missing Values"
        )

        # Duplicate records tab

        duplicate_tab = QWidget()
        duplicate_layout = QVBoxLayout(duplicate_tab)

        duplicate_layout.addWidget(
            QLabel(
                "Select the duplicate rows you want to delete. "
                "The first occurrence is retained automatically."
            )
        )

        self.duplicate_table = QTableWidget()

        self.duplicate_table.setColumnCount(3)

        self.duplicate_table.setHorizontalHeaderLabels([
            "Delete",
            "Excel Row",
            "Record Preview"
        ])

        self.configure_table(self.duplicate_table)

        duplicate_layout.addWidget(
            self.duplicate_table
        )

        self.duplicate_count_label = QLabel(
            "Duplicate rows: 0"
        )

        duplicate_layout.addWidget(
            self.duplicate_count_label
        )

        self.tabs.addTab(
            duplicate_tab,
            "Duplicate Records"
        )

        # Inconsistency tab

        inconsistency_tab = QWidget()
        inconsistency_layout = QVBoxLayout(
            inconsistency_tab
        )

        inconsistency_layout.addWidget(
            QLabel(
                "Review inconsistent text values and enter "
                "the corrected value for each affected cell."
            )
        )

        self.inconsistency_table = QTableWidget()

        self.inconsistency_table.setColumnCount(5)

        self.inconsistency_table.setHorizontalHeaderLabels([
            "Excel Row",
            "Name",
            "Column",
            "Original Value",
            "Corrected Value"
        ])

        self.configure_table(
            self.inconsistency_table
        )

        inconsistency_layout.addWidget(
            self.inconsistency_table
        )

        self.inconsistency_count_label = QLabel(
            "Inconsistent values: 0"
        )

        inconsistency_layout.addWidget(
            self.inconsistency_count_label
        )

        self.tabs.addTab(
            inconsistency_tab,
            "Inconsistencies"
        )

        # Bottom buttons

        button_layout = QHBoxLayout()

        self.apply_button = QPushButton(
            "Save Corrections"
        )

        self.cancel_button = QPushButton(
            "Cancel"
        )

        self.cancel_button.setObjectName(
            "cancelButton"
        )

        self.apply_button.clicked.connect(
            self.save_corrections
        )

        self.cancel_button.clicked.connect(
            self.reject
        )

        button_layout.addStretch()

        button_layout.addWidget(
            self.cancel_button
        )

        button_layout.addWidget(
            self.apply_button
        )

        main_layout.addLayout(button_layout)

    # --------------------------------------------------
    # TABLE CONFIGURATION
    # --------------------------------------------------

    def configure_table(self, table):

        table.setAlternatingRowColors(True)

        table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        table.setEditTriggers(
            QAbstractItemView.AllEditTriggers
        )

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        table.verticalHeader().setVisible(False)

    # --------------------------------------------------
    # MISSING VALUE DETECTION
    # --------------------------------------------------

    def load_missing_values(self):

        missing_cells = []

        for row_index in range(len(self.df)):

            for column in self.df.columns:

                value = self.df.iloc[row_index][column]

                is_missing = pd.isna(value)

                is_blank = (
                    isinstance(value, str)
                    and value.strip() == ""
                )

                if is_missing or is_blank:

                    missing_cells.append(
                        (row_index, column, value)
                    )

        self.missing_table.setRowCount(
            len(missing_cells)
        )

        for table_row, item in enumerate(missing_cells):

            row_index, column, value = item

            excel_row = row_index + 2
            person_name = self.get_person_name(row_index)

            values = [
                str(excel_row),
                person_name,
                str(column),
                "",
                ""
            ]

            for col_index, text in enumerate(values):

                cell = QTableWidgetItem(text)

                if col_index < 4:

                    cell.setFlags(
                        cell.flags()
                        & ~Qt.ItemIsEditable
                    )

                self.missing_table.setItem(
                    table_row,
                    col_index,
                    cell
                )

        self.missing_count_label.setText(
            f"Missing values detected: {len(missing_cells)}"
        )

    # --------------------------------------------------
    # DUPLICATE DETECTION
    # --------------------------------------------------

    def load_duplicates(self):

        duplicate_indexes = self.df.index[
            self.df.duplicated(keep="first")
        ].tolist()

        self.duplicate_table.setRowCount(
            len(duplicate_indexes)
        )

        for table_row, dataframe_index in enumerate(
            duplicate_indexes
        ):

            excel_row = dataframe_index + 2

            checkbox = QTableWidgetItem()

            checkbox.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsUserCheckable
            )

            checkbox.setCheckState(
                Qt.Unchecked
            )

            self.duplicate_table.setItem(
                table_row,
                0,
                checkbox
            )

            row_number = QTableWidgetItem(
                str(excel_row)
            )

            row_number.setFlags(
                row_number.flags()
                & ~Qt.ItemIsEditable
            )

            self.duplicate_table.setItem(
                table_row,
                1,
                row_number
            )

            record = self.df.iloc[
                self.df.index.get_loc(dataframe_index)
            ]

            preview = QTableWidgetItem(
                str(record.to_dict())
            )

            preview.setFlags(
                preview.flags()
                & ~Qt.ItemIsEditable
            )

            self.duplicate_table.setItem(
                table_row,
                2,
                preview
            )

        self.duplicate_count_label.setText(
            f"Duplicate rows detected: {len(duplicate_indexes)}"
        )

    # --------------------------------------------------
    # INCONSISTENCY DETECTION
    # --------------------------------------------------

    def load_inconsistencies(self):

        inconsistent_cells = []

        for column in self.df.select_dtypes(
            include=["object", "str"]
        ).columns:

            groups = {}

            for row_index, value in self.df[column].items():

                if isinstance(value, str) and value.strip():

                    key = value.strip().casefold()

                    groups.setdefault(key, set())

                    groups[key].add(value.strip())

            for row_index, value in self.df[column].items():

                if not isinstance(value, str):
                    continue

                if not value.strip():
                    continue

                key = value.strip().casefold()

                if len(groups.get(key, set())) > 1:

                    inconsistent_cells.append(
                        (row_index, column, value)
                    )

        self.inconsistency_table.setRowCount(
            len(inconsistent_cells)
        )

        for table_row, item in enumerate(
            inconsistent_cells
        ):

            row_index, column, original_value = item

            excel_row = row_index + 2
            person_name = self.get_person_name(row_index)

            values = [
                str(excel_row),
                person_name,
                str(column),
                original_value,
                ""
            ]

            for col_index, text in enumerate(values):

                cell = QTableWidgetItem(text)

                if col_index < 4:

                    cell.setFlags(
                        cell.flags()
                        & ~Qt.ItemIsEditable
                    )

                self.inconsistency_table.setItem(
                    table_row,
                    col_index,
                    cell
                )

        self.inconsistency_count_label.setText(
            f"Inconsistent values detected: "
            f"{len(inconsistent_cells)}"
        )

    # --------------------------------------------------
    # SAVE MANUAL CORRECTIONS
    # --------------------------------------------------

    def save_corrections(self):

        self.missing_changes = []
        self.duplicate_rows = []
        self.inconsistency_changes = []

        # Missing value corrections

        for row in range(
            self.missing_table.rowCount()
        ):

            excel_row = int(
                self.missing_table.item(row, 0).text()
            )

            column = (
                self.missing_table.item(row, 2).text()
            )

            new_value = (
                self.missing_table.item(row, 4).text()
            )

            if new_value.strip():

                dataframe_index = excel_row - 2

                self.missing_changes.append({
                    "row_index": dataframe_index,
                    "excel_row": excel_row,
                    "column": column,
                    "new_value": new_value
                })

        # Duplicate row selections

        for row in range(
            self.duplicate_table.rowCount()
        ):

            checkbox = self.duplicate_table.item(
                row, 0
            )

            if checkbox.checkState() == Qt.Checked:

                excel_row = int(
                    self.duplicate_table.item(
                        row, 1
                    ).text()
                )

                self.duplicate_rows.append(
                    excel_row - 2
                )

        # Inconsistency corrections

        for row in range(
            self.inconsistency_table.rowCount()
        ):

            excel_row = int(
                self.inconsistency_table.item(
                    row, 0
                ).text()
            )

            column = (
                self.inconsistency_table.item(
                    row, 2
                ).text()
            )

            original_value = (
                self.inconsistency_table.item(
                    row, 3
                ).text()
            )

            corrected_value = (
                self.inconsistency_table.item(
                    row, 4
                ).text()
            )

            if corrected_value.strip():

                self.inconsistency_changes.append({
                    "row_index": excel_row - 2,
                    "excel_row": excel_row,
                    "column": column,
                    "old_value": original_value,
                    "new_value": corrected_value
                })

        total_changes = (
            len(self.missing_changes)
            + len(self.duplicate_rows)
            + len(self.inconsistency_changes)
        )

        if total_changes == 0:

            QMessageBox.information(
                self,
                "No Corrections",
                "You have not entered or selected any corrections."
            )

            return

        QMessageBox.information(
            self,
            "Corrections Saved",
            f"Manual corrections prepared successfully.\n\n"
            f"Missing values to fill: "
            f"{len(self.missing_changes)}\n"
            f"Duplicate rows to delete: "
            f"{len(self.duplicate_rows)}\n"
            f"Inconsistent values to update: "
            f"{len(self.inconsistency_changes)}\n\n"
            "These changes are not yet applied to your dataset."
        )

        self.accept()

    # --------------------------------------------------
    # RETURN CORRECTIONS
    # --------------------------------------------------

    def get_corrections(self):

        return {
            "missing_changes": self.missing_changes,
            "duplicate_rows": self.duplicate_rows,
            "inconsistency_changes": self.inconsistency_changes
        }
