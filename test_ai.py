
from ai_analysis import analyze_quality_issues


test_issues = [
    {
        "issue_name": "Missing values",
        "column": "Email",
        "count": 1
    },
    {
        "issue_name": "Invalid email addresses",
        "column": "Email",
        "count": 2
    },
    {
        "issue_name": "Duplicate records",
        "column": "Multiple columns",
        "count": 1
    },
    {
        "issue_name": "Invalid age values",
        "column": "Age",
        "count": 3
    }
]

test_profile = {
    "total_rows": 52,
    "total_columns": 13,
    "duplicate_rows": 1
}


print("\nPurifData - Gemini AI Analysis Test")
print("-" * 45)

result = analyze_quality_issues(
    test_issues,
    test_profile
)

print("\nAI ANALYSIS RESULT")
print("-" * 45)
print(result)
