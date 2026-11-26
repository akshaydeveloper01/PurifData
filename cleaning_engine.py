
import os
import pandas as pd


# --------------------------------------------------
# READ ORIGINAL DATASET
# --------------------------------------------------

def read_original_dataset(file_path):

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":

        return pd.read_csv(file_path)

    elif extension in [".xlsx", ".xls"]:

        return pd.read_excel(file_path)

    else:

        raise ValueError("Unsupported dataset format.")


# --------------------------------------------------
# GENERATE OUTPUT FILE PATH
# --------------------------------------------------

def get_output_path(file_path):

    folder = os.path.dirname(file_path)

    file_name = os.path.basename(file_path)

    name, extension = os.path.splitext(file_name)

    output_path = os.path.join(
        folder,
        f"{name}_cleaned{extension}"
    )

    counter = 1

    while os.path.exists(output_path):

        output_path = os.path.join(
            folder,
            f"{name}_cleaned_{counter}{extension}"
        )

        counter += 1

    return output_path


# --------------------------------------------------
# SAVE CLEANED DATASET
# --------------------------------------------------

def save_cleaned_dataset(df, output_path):

    extension = os.path.splitext(output_path)[1].lower()

    if extension == ".csv":

        df.to_csv(
            output_path,
            index=False
        )

    elif extension in [".xlsx", ".xls"]:

        if extension == ".xls":

            raise ValueError(
                "Saving .xls files is not supported. "
                "Please use .xlsx or .csv."
            )

        df.to_excel(
            output_path,
            index=False
        )

    else:

        raise ValueError("Unsupported output format.")


# --------------------------------------------------
# VALIDATE MANUAL CORRECTIONS
# --------------------------------------------------

def validate_corrections(df, corrections):

    missing_changes = corrections.get(
        "missing_changes", []
    )

    duplicate_rows = corrections.get(
        "duplicate_rows", []
    )

    inconsistency_changes = corrections.get(
        "inconsistency_changes", []
    )

    for item in missing_changes:

        row_index = item.get("row_index")
        column = item.get("column")

        if not isinstance(row_index, int):
            raise ValueError("Invalid missing-value row index.")

        if row_index < 0 or row_index >= len(df):
            raise ValueError("Missing-value row is outside the dataset.")

        if column not in df.columns:
            raise ValueError(f"Column not found: {column}")

        if pd.notna(df.iloc[row_index][column]):

            current_value = df.iloc[row_index][column]

            if not (
                isinstance(current_value, str)
                and current_value.strip() == ""
            ):

                raise ValueError(
                    f"Row {item.get('excel_row')} in "
                    f"'{column}' is no longer missing."
                )

        if not str(item.get("new_value", "")).strip():

            raise ValueError(
                "A missing-value correction contains an empty value."
            )

    for row_index in duplicate_rows:

        if not isinstance(row_index, int):
            raise ValueError("Invalid duplicate row index.")

        if row_index < 0 or row_index >= len(df):
            raise ValueError("Duplicate row is outside the dataset.")

        if not df.iloc[:row_index].eq(
            df.iloc[row_index]
        ).all(axis=1).any():

            raise ValueError(
                f"Selected row {row_index + 2} is not an exact "
                "duplicate of an earlier row."
            )

    for item in inconsistency_changes:

        row_index = item.get("row_index")
        column = item.get("column")

        if not isinstance(row_index, int):
            raise ValueError("Invalid inconsistency row index.")

        if row_index < 0 or row_index >= len(df):
            raise ValueError("Inconsistency row is outside the dataset.")

        if column not in df.columns:
            raise ValueError(f"Column not found: {column}")

        current_value = df.iloc[row_index][column]

        if str(current_value) != str(item.get("old_value")):

            raise ValueError(
                f"The original value at row {row_index + 2}, "
                f"column '{column}' has changed."
            )

        if not str(item.get("new_value", "")).strip():

            raise ValueError(
                "An inconsistency correction contains an empty value."
            )


# --------------------------------------------------
# APPLY MANUAL CORRECTIONS
# --------------------------------------------------

def apply_manual_corrections(df, corrections):

    cleaned_df = df.copy(deep=True)

    results = []

    missing_changes = corrections.get(
        "missing_changes", []
    )

    duplicate_rows = corrections.get(
        "duplicate_rows", []
    )

    inconsistency_changes = corrections.get(
        "inconsistency_changes", []
    )

    # ----------------------------------------------
    # 1. FILL MISSING VALUES
    # ----------------------------------------------

    filled_count = 0

    for item in missing_changes:

        row_index = item["row_index"]
        column = item["column"]
        new_value = item["new_value"]

        cleaned_df.iat[
            row_index,
            cleaned_df.columns.get_loc(column)
        ] = new_value

        filled_count += 1

    results.append({

        "operation": "Manual Missing Value Correction",

        "status": "Completed",

        "affected": filled_count,

        "details": (
            f"{filled_count} missing cells filled "
            "with user-entered values."
        )
    })

    # ----------------------------------------------
    # 2. DELETE SELECTED DUPLICATE ROWS
    # ----------------------------------------------

    deleted_count = 0

    if duplicate_rows:

        # Validate against the original dataframe.
        # Delete by positional index to avoid duplicate
        # DataFrame index labels causing accidental deletion.

        positions_to_keep = [
            position
            for position in range(len(cleaned_df))
            if position not in set(duplicate_rows)
        ]

        cleaned_df = cleaned_df.iloc[
            positions_to_keep
        ].copy()

        deleted_count = len(duplicate_rows)

    results.append({

        "operation": "Manual Duplicate Removal",

        "status": "Completed",

        "affected": deleted_count,

        "details": (
            f"{deleted_count} user-selected duplicate rows deleted."
        )
    })

    # ----------------------------------------------
    # 3. CORRECT INCONSISTENT VALUES
    # ----------------------------------------------

    corrected_count = 0

    # Use original row positions to locate cells.
    # Account for deleted rows by tracking their positions.

    deleted_positions = set(duplicate_rows)

    for item in inconsistency_changes:

        original_position = item["row_index"]

        if original_position in deleted_positions:
            continue

        # Count how many earlier rows were deleted.
        removed_before = sum(
            1
            for position in deleted_positions
            if position < original_position
        )

        new_position = original_position - removed_before

        column = item["column"]

        cleaned_df.iat[
            new_position,
            cleaned_df.columns.get_loc(column)
        ] = item["new_value"]

        corrected_count += 1

    results.append({

        "operation": "Manual Inconsistency Correction",

        "status": "Completed",

        "affected": corrected_count,

        "details": (
            f"{corrected_count} inconsistent values updated "
            "with user-entered corrections."
        )
    })

    return cleaned_df, results


# --------------------------------------------------
# MAIN CLEANING FUNCTION
# --------------------------------------------------

def clean_dataset(file_path, cleaning_plan=None, corrections=None):

    if not os.path.isfile(file_path):

        raise FileNotFoundError(
            "Original dataset was not found."
        )

    original_df = read_original_dataset(file_path)

    # Accept corrections directly or as the third argument.
    # No automatic filling or cleaning is performed.

    if corrections is None:

        corrections = {}

    validate_corrections(
        original_df,
        corrections
    )

    total_changes = (
        len(corrections.get("missing_changes", []))
        + len(corrections.get("duplicate_rows", []))
        + len(corrections.get("inconsistency_changes", []))
    )

    if total_changes == 0:

        raise ValueError(
            "No manual corrections were selected."
        )

    cleaned_df, results = apply_manual_corrections(
        original_df,
        corrections
    )

    output_path = get_output_path(file_path)

    save_cleaned_dataset(
        cleaned_df,
        output_path
    )

    return {

        "original_file": file_path,

        "cleaned_file": output_path,

        "original_rows": len(original_df),

        "cleaned_rows": len(cleaned_df),

        "rows_removed": (
            len(original_df) - len(cleaned_df)
        ),

        "total_operations": len(results),

        "approved_operations": total_changes,

        "results": results,

        "manual_corrections": corrections
    }
