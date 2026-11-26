
import os
import pandas as pd


def read_dataset(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":

        return pd.read_csv(file_path)

    elif extension in [".xlsx", ".xls"]:

        return pd.read_excel(file_path)

    else:

        raise ValueError("Unsupported dataset format.")


# --------------------------------------------------
# GENERATE MANUAL CLEANING PREVIEW
# --------------------------------------------------

def generate_cleaning_preview(
    file_path,
    cleaning_plan=None,
    corrections=None
):

    if not os.path.isfile(file_path):

        raise FileNotFoundError(
            "Dataset file was not found."
        )

    if corrections is None:
        corrections = {}

    df = read_dataset(file_path)

    preview = []

    missing_changes = corrections.get(
        "missing_changes", []
    )

    duplicate_rows = corrections.get(
        "duplicate_rows", []
    )

    inconsistency_changes = corrections.get(
        "inconsistency_changes", []
    )

    # --------------------------------------------------
    # 1. DATASET OVERVIEW
    # --------------------------------------------------

    preview.append({

        "operation": "Dataset Overview",

        "description": "Original dataset information.",

        "affected": 0,

        "status": "Information",

        "details": (
            f"Rows: {len(df)} | "
            f"Columns: {len(df.columns)} | "
            f"Missing cells: {int(df.isna().sum().sum())} | "
            f"Duplicate rows: {int(df.duplicated().sum())}"
        )
    })

    # --------------------------------------------------
    # 2. MISSING VALUE CORRECTIONS
    # --------------------------------------------------

    valid_missing = []

    for item in missing_changes:

        row_index = item.get("row_index")
        column = item.get("column")
        new_value = item.get("new_value")

        if (
            not isinstance(row_index, int)
            or row_index < 0
            or row_index >= len(df)
            or column not in df.columns
            or not str(new_value).strip()
        ):

            continue

        current_value = df.iloc[row_index][column]

        is_missing = pd.isna(current_value)

        is_blank = (
            isinstance(current_value, str)
            and current_value.strip() == ""
        )

        if is_missing or is_blank:

            valid_missing.append(item)

    if valid_missing:

        details = []

        for item in valid_missing:

            details.append(
                f"Excel Row {item['excel_row']} | "
                f"Column: {item['column']} | "
                f"New Value: {item['new_value']}"
            )

        preview.append({

            "operation": "Manual Missing Value Correction",

            "description": (
                "Fill missing cells using values entered "
                "by the user."
            ),

            "affected": len(valid_missing),

            "status": "Ready for Approval",

            "details": "\n".join(details)
        })

    else:

        preview.append({

            "operation": "Manual Missing Value Correction",

            "description": "No missing-value corrections entered.",

            "affected": 0,

            "status": "No Changes",

            "details": (
                "Missing cells will remain unchanged."
            )
        })

    # --------------------------------------------------
    # 3. DUPLICATE ROW DELETION
    # --------------------------------------------------

    valid_duplicates = []

    for row_index in duplicate_rows:

        if (
            not isinstance(row_index, int)
            or row_index < 0
            or row_index >= len(df)
        ):

            continue

        # Check whether the row is an exact duplicate
        # of an earlier row.

        duplicate_found = df.iloc[:row_index].eq(
            df.iloc[row_index]
        ).all(axis=1).any()

        if duplicate_found:

            valid_duplicates.append(row_index)

    if valid_duplicates:

        details = "\n".join(
            [
                f"Excel Row {row_index + 2} will be deleted."
                for row_index in valid_duplicates
            ]
        )

        preview.append({

            "operation": "Manual Duplicate Removal",

            "description": (
                "Delete only duplicate rows selected by the user."
            ),

            "affected": len(valid_duplicates),

            "status": "Ready for Approval",

            "details": details
        })

    else:

        preview.append({

            "operation": "Manual Duplicate Removal",

            "description": "No duplicate rows selected for deletion.",

            "affected": 0,

            "status": "No Changes",

            "details": (
                "The dataset's duplicate rows will remain unchanged."
            )
        })

    # --------------------------------------------------
    # 4. INCONSISTENCY CORRECTIONS
    # --------------------------------------------------

    valid_inconsistencies = []

    deleted_positions = set(valid_duplicates)

    for item in inconsistency_changes:

        row_index = item.get("row_index")
        column = item.get("column")

        old_value = item.get("old_value")
        new_value = item.get("new_value")

        if (
            not isinstance(row_index, int)
            or row_index < 0
            or row_index >= len(df)
            or column not in df.columns
            or row_index in deleted_positions
            or not str(new_value).strip()
        ):

            continue

        current_value = df.iloc[row_index][column]

        if str(current_value) == str(old_value):

            valid_inconsistencies.append(item)

    if valid_inconsistencies:

        details = []

        for item in valid_inconsistencies:

            details.append(
                f"Excel Row {item['excel_row']} | "
                f"Column: {item['column']} | "
                f"{item['old_value']} -> {item['new_value']}"
            )

        preview.append({

            "operation": "Manual Inconsistency Correction",

            "description": (
                "Update inconsistent values using "
                "user-entered corrections."
            ),

            "affected": len(valid_inconsistencies),

            "status": "Ready for Approval",

            "details": "\n".join(details)
        })

    else:

        preview.append({

            "operation": "Manual Inconsistency Correction",

            "description": "No inconsistency corrections entered.",

            "affected": 0,

            "status": "No Changes",

            "details": (
                "Inconsistent values will remain unchanged."
            )
        })

    # --------------------------------------------------
    # 5. TOTAL CHANGE SUMMARY
    # --------------------------------------------------

    total_changes = (
        len(valid_missing)
        + len(valid_duplicates)
        + len(valid_inconsistencies)
    )

    preview.append({

        "operation": "Total Proposed Changes",

        "description": (
            "Summary of all manual corrections."
        ),

        "affected": total_changes,

        "status": (
            "Ready for Review"
            if total_changes > 0
            else "No Changes"
        ),

        "details": (
            f"Missing values to fill: {len(valid_missing)}\n"
            f"Duplicate rows to delete: {len(valid_duplicates)}\n"
            f"Inconsistent values to update: "
            f"{len(valid_inconsistencies)}\n"
            f"Total changes: {total_changes}"
        )
    })

    return preview
