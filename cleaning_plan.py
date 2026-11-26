
# --------------------------------------------------
# PURIFDATA - CLEANING PLAN GENERATOR
# --------------------------------------------------

def generate_cleaning_plan(issue_summary):

    cleaning_plan = []

    for issue in issue_summary:

        issue_name = str(issue.get("issue_name", ""))
        column = str(issue.get("column", "Unknown"))
        count = int(issue.get("count", 0))

        name = issue_name.lower()

        action = ""
        priority = "Medium"
        strategy = None

        # 1. Missing Values
        if "missing values" in name:

            action = (
                "Review missing values. Select a suitable "
                "filling strategy only after user approval."
            )

            if column.lower() in ["email", "phone", "name"]:
                priority = "High"
                action = (
                    "Find missing information using a trusted "
                    "source. Do not invent values."
                )

        # 2. Blank Values
        elif "blank values" in name:

            action = (
                "Convert blank entries into missing values."
            )

            priority = "High" if column.lower() == "name" else "Medium"

        # 3. Duplicate Records
        elif "duplicate records" in name or "duplicate rows" in name:

            action = (
                "Remove exact duplicate rows and retain one copy."
            )

            priority = "High"

        # 4. Invalid Email
        elif "invalid email" in name:

            action = (
                "Identify invalid email formats. Flag them "
                "for manual correction."
            )

            priority = "High"

        # 5. Invalid Phone
        elif "invalid phone" in name:

            action = (
                "Identify invalid phone numbers and verify "
                "them before correction."
            )

            priority = "High"

        # 6. Invalid Age
        elif "invalid age" in name:

            action = (
                "Convert non-numeric age values into missing "
                "values. Review out-of-range ages manually."
            )

            priority = "Medium"

        # 7. Invalid Salary
        elif "invalid salary" in name:

            action = (
                "Convert non-numeric salary values into missing "
                "values. Verify other unusual values manually."
            )

            priority = "Medium"

        # 8. Other invalid numeric values
        elif "invalid numeric" in name or "invalid number" in name:

            action = (
                "Convert non-numeric values into missing values "
                "while preserving valid numbers."
            )

            priority = "Medium"

        # 9. Text inconsistencies
        elif any(word in name for word in [
            "inconsistent", "standardiz",
            "capitalization", "case mismatch",
            "text formatting"
        ]):

            action = (
                "Standardize capitalization and whitespace "
                "using the most common existing spelling."
            )

            priority = "Low"

        # 10. Suspicious Zero Salary
        elif "zero salary" in name:

            action = (
                "Verify whether zero salary is intentional. "
                "Do not change it automatically."
            )

            priority = "Medium"

        # 11. Invalid Dates
        elif "invalid joining dates" in name or "invalid date" in name:

            action = (
                "Review invalid dates and standardize them "
                "after confirming the correct date format."
            )

            priority = "Medium"

        # 12. Gender
        elif "gender" in name:

            action = (
                "Review unrecognized gender values and map "
                "them only when their meaning is clear."
            )

            priority = "Low"

        # 13. Status
        elif "status" in name:

            action = (
                "Review unrecognized status values and map "
                "them to approved categories."
            )

            priority = "Low"

        # 14. City
        elif "city" in name:

            action = (
                "Review city names and standardize only "
                "clearly identifiable text inconsistencies."
            )

            priority = "Low"

        # 15. State
        elif "state" in name:

            action = (
                "Standardize state names using an approved "
                "reference mapping."
            )

            priority = "Low"

        else:

            action = (
                "Review the detected issue and determine "
                "an appropriate correction."
            )

        cleaning_plan.append({

            "issue_name": issue_name,

            "column": column,

            "count": count,

            "action": action,

            "priority": priority,

            "review_required": "Required",

            "approval_required": True,

            "approved": False,

            "approval_status": "Pending",

            "strategy": strategy

        })

    # High priority first
    priority_order = {
        "High": 1,
        "Medium": 2,
        "Low": 3
    }

    cleaning_plan.sort(
        key=lambda item: priority_order[item["priority"]]
    )

    return cleaning_plan
