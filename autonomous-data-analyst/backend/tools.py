"""Provide deterministic pandas analysis and matplotlib chart tools."""

from langchain_core.tools import tool
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import uuid
from typing import Optional


DATAFRAME = None
DATASET_NAME = None
# Analysis tools read this shared dataframe because LangChain invokes them
# independently; the API refreshes it whenever a session sends a chat request.
CHART_DIR = Path(__file__).parent / "charts"
CHART_DIR.mkdir(exist_ok=True)

MAX_TOOL_OUTPUT_CHARS = 3500
MAX_PREVIEW_ROWS = 5
MAX_PREVIEW_COLUMNS = None
MAX_METADATA_COLUMNS = 60
MAX_ERROR_COLUMNS = 25


def _truncate_output(text: str) -> str:
    if len(text) <= MAX_TOOL_OUTPUT_CHARS:
        return text
    return (
        text[: MAX_TOOL_OUTPUT_CHARS - 100]
        + "\n\n[Output truncated to control token usage. Ask for a narrower query for full details.]"
    )


def _compact_df_preview(df: pd.DataFrame, rows: int = MAX_PREVIEW_ROWS, cols: Optional[int] = MAX_PREVIEW_COLUMNS) -> str:
    preview = df.iloc[:rows] if cols is None else df.iloc[:rows, :cols]
    text = preview.to_string(index=False)
    notes = []

    if df.shape[0] > rows:
        notes.append(f"showing first {rows} rows")
    if cols is not None and df.shape[1] > cols:
        notes.append(f"first {cols} of {df.shape[1]} columns")

    if notes:
        text += "\n(" + ", ".join(notes) + ")"

    return text


def _available_columns_hint(limit: int = MAX_ERROR_COLUMNS) -> str:
    if DATAFRAME is None:
        return "No dataset loaded."

    cols = [str(col) for col in DATAFRAME.columns]
    if len(cols) <= limit:
        return ", ".join(cols)

    remaining = len(cols) - limit
    return ", ".join(cols[:limit]) + f", ... (+{remaining} more)"


def set_dataframe(df: pd.DataFrame, dataset_name: str):
    # LangChain tool calls do not receive the API session directly, so the API
    # refreshes this shared context immediately before invoking the agent.
    global DATAFRAME, DATASET_NAME
    DATAFRAME = df
    DATASET_NAME = dataset_name

@tool
def inspect_data() -> str:
    """Inspect the uploaded dataset. Returns row count, column count, data types, missing values, duplicate count, and sample records."""
    
    print("[CALL] inspect_data")
    if DATAFRAME is None:
        return "No dataset has been uploaded."

    result = []
    result.append(f"Dataset_Name: {DATASET_NAME}")
    result.append(f"Rows: {len(DATAFRAME)}")
    result.append(f"Columns: {len(DATAFRAME.columns)}")
    result.append(f"Duplicate Rows: {DATAFRAME.duplicated().sum()}")
    result.append("\nColumns and Data Types:")

    columns_to_show = list(DATAFRAME.columns[:MAX_METADATA_COLUMNS])

    for column in columns_to_show:
        dtype = DATAFRAME.dtypes[column]
        result.append(f"- {column}: {dtype}")

    if len(DATAFRAME.columns) > MAX_METADATA_COLUMNS:
        remaining = len(DATAFRAME.columns) - MAX_METADATA_COLUMNS
        result.append(f"- ... (+{remaining} more columns)")

    result.append("\nMissing Values:")

    missing_values = DATAFRAME.isnull().sum()
    missing_nonzero = missing_values[missing_values > 0]

    if missing_nonzero.empty:
        result.append("- None")
    else:
        for column, missing in missing_nonzero.items():
            result.append(f"- {column}: {missing}")

    zero_missing_columns = int((missing_values == 0).sum())
    if zero_missing_columns > 0:
        result.append(f"- Columns with no missing values: {zero_missing_columns}")

    return _truncate_output("\n".join(result))

@tool
def analyze_data(operation: str, column: str = "", group_by: str = "", filter_column: str = "", filter_value: str = "", second_column: str = "", top_n: int = 5) -> str:
    """Analyze the uploaded dataset using operations such as summary, count, sum, mean, median, min, max, std, variance, unique, value_counts, groupby, filter, sort, top_n, percentage, correlation, describe, and trend.

Analyze the uploaded dataset.

Supported operations and required parameters:

- summary / describe:
  Returns descriptive statistics for the entire dataset.

- count:
  Required: column

- sum, mean, median, min, max, std, variance:
  Required: column (must be numeric)

- unique:
  Required: column
  Optional: top_n (number of unique values to return)

- value_counts:
  Required: column
  Optional: top_n (return the top N most frequent values)

- groupby:
  Required: group_by, column
  Optional: top_n (return the top N groups sorted by total sum)
  Returns the top N rows sorted in descending order.

- filter:
  Required: filter_column, filter_value
  Optional: top_n (limit returned rows)

- sort:
  Required: column
  Optional: top_n (return first N sorted rows)
    Returns the top N rows sorted in descending order.

- top_n:
  Required: column, top_n
  Returns the highest N rows based on a numeric column.

- percentage:
  Required: column (numeric)
  Optional: top_n (limit displayed results)

- correlation:
  Optional: column, second_column
  If both columns are provided, returns their correlation.
  Otherwise returns the full correlation matrix.

- missing:
  Returns missing value counts for all columns.

- duplicates:
  Returns the number of duplicate rows.

- trend:
  Required: column (numeric)
  Uses the detected datetime column to generate a time-based trend.

Always use the appropriate parameters for the selected operation.
"""
    print(f"[CALL] analyze_data(operation={operation}, column={column})")

    if DATAFRAME is None:
        return "No dataset has been uploaded."

    operation = operation.lower().strip()

    if operation in {"summary", "describe"}:
        print(f"[METHOD] analyze_data -> {operation}")
        summary = DATAFRAME.describe(include="all").transpose().head(20)
        return _truncate_output(summary.to_string())

    if operation == "count":
        print("[METHOD] analyze_data -> count")
        if not column or column not in DATAFRAME.columns:
            return f"Valid column required. Available columns: {_available_columns_hint()}"
        return f"Count of non-null values in {column}: {DATAFRAME[column].count()}"

    if operation in {"sum", "mean", "median", "min", "max", "std", "variance"}:
        print(f"[METHOD] analyze_data -> {operation}")
        if not column or column not in DATAFRAME.columns:
            return f"Valid numeric column required. Available columns: {_available_columns_hint()}"

        if not pd.api.types.is_numeric_dtype(DATAFRAME[column]):
            return f"Column '{column}' is not numeric."

        series = DATAFRAME[column].dropna()

        if operation == "sum":
            result = series.sum()
        elif operation == "mean":
            result = series.mean()
        elif operation == "median":
            result = series.median()
        elif operation == "min":
            result = series.min()
        elif operation == "max":
            result = series.max()
        elif operation == "std":
            result = series.std()
        else:
            result = series.var()

        return f"{operation.capitalize()} of {column}: {result}"

    if operation == "unique":
        print("[METHOD] analyze_data -> unique")
        if not column or column not in DATAFRAME.columns:
            return f"Valid column required. Available columns: {_available_columns_hint()}"
        values = DATAFRAME[column].dropna().unique().tolist()
        return f"Unique values in {column} ({len(values)}): {values[:top_n]}"

    if operation == "value_counts":
        print("[METHOD] analyze_data -> value_counts")
        if not column or column not in DATAFRAME.columns:
            return f"Valid column required. Available columns: {_available_columns_hint()}"
        return _truncate_output(DATAFRAME[column].value_counts(dropna=False).head(min(top_n, 10)).to_string())

    if operation == "groupby":
        print("[METHOD] analyze_data -> groupby")
        if not group_by or group_by not in DATAFRAME.columns:
            return f"Valid group_by column required. Available columns: {_available_columns_hint()}"

        if not column or column not in DATAFRAME.columns:
            return f"Valid numeric column required. Available columns: {_available_columns_hint()}"

        if not pd.api.types.is_numeric_dtype(DATAFRAME[column]):
            return f"Column '{column}' is not numeric."

        result = DATAFRAME.groupby(group_by)[column].agg(["count", "sum", "mean", "median", "min", "max"]).sort_values("sum", ascending=False)

        return _truncate_output(result.head(min(top_n, 10)).to_string())

    if operation == "filter":
        print("[METHOD] analyze_data -> filter")
        if not filter_column or filter_column not in DATAFRAME.columns:
            return f"Valid filter_column required. Available columns: {_available_columns_hint()}"

        filtered = DATAFRAME[DATAFRAME[filter_column].astype(str).str.lower() == str(filter_value).lower()]

        if filtered.empty:
            return f"No rows found where {filter_column} = {filter_value}."

        return _truncate_output(_compact_df_preview(filtered, rows=min(top_n, 10)))

    if operation == "sort":
        print("[METHOD] analyze_data -> sort")
        if not column or column not in DATAFRAME.columns:
            return f"Valid column required. Available columns: {_available_columns_hint()}"

        result = DATAFRAME.sort_values(column, ascending=False)

        return _truncate_output(_compact_df_preview(result, rows=min(top_n, 10)))

    if operation == "top_n":
        print("[METHOD] analyze_data -> top_n")
        if not column or column not in DATAFRAME.columns:
            return f"Valid numeric column required. Available columns: {_available_columns_hint()}"

        if not pd.api.types.is_numeric_dtype(DATAFRAME[column]):
            return f"Column '{column}' is not numeric."
        top_n = min(top_n, 10)
        return _truncate_output(_compact_df_preview(DATAFRAME.nlargest(top_n, column), rows=min(top_n, 10)))

    if operation == "percentage":
        print("[METHOD] analyze_data -> percentage")
        if not column or column not in DATAFRAME.columns:
            return f"Valid numeric column required. Available columns: {_available_columns_hint()}"

        if not pd.api.types.is_numeric_dtype(DATAFRAME[column]):
            return f"Column '{column}' is not numeric."

        total = DATAFRAME[column].sum()

        if total == 0:
            return f"Total of {column} is 0, so percentage cannot be calculated."

        result = ((DATAFRAME[column] / total) * 100).head(min(top_n, 10)).round(3)

        return _truncate_output(result.to_string())

    if operation == "correlation":
        print("[METHOD] analyze_data -> correlation")
        if column and second_column:
            if column not in DATAFRAME.columns or second_column not in DATAFRAME.columns:
                return f"Columns must exist in dataset. Available columns: {_available_columns_hint()}"

            if not pd.api.types.is_numeric_dtype(DATAFRAME[column]) or not pd.api.types.is_numeric_dtype(DATAFRAME[second_column]):
                return "Both columns must be numeric."

            correlation = DATAFRAME[[column, second_column]].corr().iloc[0, 1]

            return f"Correlation between {column} and {second_column}: {correlation}"

        numeric_data = DATAFRAME.select_dtypes(include="number")

        if numeric_data.empty:
            return "No numeric columns are available for correlation analysis."

        return _truncate_output(numeric_data.corr().round(4).to_string())

    if operation == "missing":
        print("[METHOD] analyze_data -> missing")
        result = DATAFRAME.isnull().sum().sort_values(ascending=False)
        result = result[result > 0]

        if result.empty:
            return "There are no missing values in the dataset."

        return _truncate_output(result.to_string())

    if operation == "duplicates":
        print("[METHOD] analyze_data -> duplicates")
        return f"Duplicate rows: {DATAFRAME.duplicated().sum()}"

    if operation == "trend":
        print("[METHOD] analyze_data -> trend")
        if not column or column not in DATAFRAME.columns:
            return f"Valid numeric column required. Available columns: {_available_columns_hint()}"

        date_column = ""

        for candidate in DATAFRAME.columns:
            if pd.api.types.is_datetime64_any_dtype(DATAFRAME[candidate]):
                date_column = candidate
                break

        if not date_column:
            return "No datetime column was detected for trend analysis."

        if not pd.api.types.is_numeric_dtype(DATAFRAME[column]):
            return f"Column '{column}' must be numeric for trend analysis."

        result = DATAFRAME.groupby(date_column)[column].sum().sort_index()
        return _truncate_output(result.head(20).to_string())

    return "Unsupported operation. Supported operations: summary, count, sum, mean, median, min, max, std, variance, unique, value_counts, groupby, filter, sort, top_n, percentage, correlation, missing, duplicates, trend."

@tool
def create_chart(chart_type: str, x_column: str, y_column: str = "", top_n: int = 10) -> str:
    """Create a chart from the uploaded dataset. Supported chart types are bar, line, histogram, scatter, and pie
    Create a visualization from the uploaded dataset.

    Supported chart types and required parameters:

    - bar:
      Required: x_column
      Optional: y_column, top_n
      If y_column is provided, displays the sum of y_column grouped by x_column.
      Otherwise, displays the frequency count of x_column.

    - line:
      Required: x_column, y_column
      Creates a line chart using the summed y_column grouped by x_column.

    - histogram:
      Required: x_column (must be numeric)
      Displays the distribution of a numeric column.

    - scatter:
      Required: x_column, y_column
      Both columns must be numeric.
      Displays the relationship between two numeric variables.

    - pie:
      Required: x_column
      Optional: top_n
      Displays the proportion of the top N categories in x_column.

    Parameters:
    - chart_type: Type of visualization (bar, line, histogram, scatter, pie).
    - x_column: Column used for the x-axis or category.
    - y_column: Numeric column used for aggregation or the y-axis.
    - top_n: Maximum number of categories to display (default 10).

    Returns:
    - CHART_PATH:<filename> when the chart is successfully created.
    - An error message if validation fails.
    """
    print(f"[CALL] create_chart(chart_type={chart_type}, x_column={x_column}, y_column={y_column})")

    if DATAFRAME is None:
        return "No dataset has been uploaded."

    chart_type = chart_type.lower().strip()

    if x_column not in DATAFRAME.columns:
        return f"Column '{x_column}' does not exist. Available columns: {list(DATAFRAME.columns)}"

    if y_column and y_column not in DATAFRAME.columns:
        return f"Column '{y_column}' does not exist. Available columns: {list(DATAFRAME.columns)}"

    fig, ax = plt.subplots(figsize=(7, 5))

    if chart_type == "bar":
        print("[METHOD] create_chart -> bar")

        if y_column:
            chart_data = DATAFRAME.groupby(x_column)[y_column].sum().sort_values(ascending=False).head(top_n)
            chart_data.plot(kind="bar", ax=ax)
            ax.set_xlabel(x_column)
            ax.set_ylabel(y_column)
            ax.set_title(f"{y_column} by {x_column}")
        else:
            chart_data = DATAFRAME[x_column].value_counts().head(top_n)
            chart_data.plot(kind="bar", ax=ax)
            ax.set_xlabel(x_column)
            ax.set_ylabel("Count")
            ax.set_title(f"Count by {x_column}")

    elif chart_type == "line":
        print("[METHOD] create_chart -> line")

        if not y_column:
            plt.close(fig)
            return "A y_column is required for a line chart."

        chart_data = DATAFRAME.groupby(x_column)[y_column].sum().sort_index()
        chart_data.plot(kind="line", marker="o", ax=ax)
        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        ax.set_title(f"{y_column} by {x_column}")

    elif chart_type == "histogram":
        print("[METHOD] create_chart -> histogram")

        if not pd.api.types.is_numeric_dtype(DATAFRAME[x_column]):
            plt.close(fig)
            return f"Column '{x_column}' must be numeric for a histogram."

        DATAFRAME[x_column].dropna().plot(kind="hist", bins=20, ax=ax)
        ax.set_xlabel(x_column)
        ax.set_title(f"Distribution of {x_column}")

    elif chart_type == "scatter":
        print("[METHOD] create_chart -> scatter")

        if not y_column or not x_column:
            plt.close(fig)
            return "Both x_column and y_column are required for a scatter plot."

        if not pd.api.types.is_numeric_dtype(DATAFRAME[x_column]) or not pd.api.types.is_numeric_dtype(DATAFRAME[y_column]):
            plt.close(fig)
            return "Both x_column and y_column must be numeric for a scatter plot."

        ax.scatter(DATAFRAME[x_column], DATAFRAME[y_column], alpha=0.6)
        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        ax.set_title(f"{y_column} vs {x_column}")

    elif chart_type == "pie":
        print("[METHOD] create_chart -> pie")

        chart_data = DATAFRAME[x_column].value_counts().head(top_n)

        if chart_data.empty:
            plt.close(fig)
            return "No data available for pie chart."

        chart_data.plot(kind="pie", autopct="%1.1f%%", ax=ax)
        ax.set_ylabel("")
        ax.set_title(f"Distribution of {x_column}")

    else:
        plt.close(fig)
        return "Unsupported chart type. Supported types: bar, line, histogram, scatter, pie."

    fig.tight_layout()

    filename = f"chart_{uuid.uuid4().hex[:8]}.png"
    filepath = CHART_DIR / filename
    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return f"CHART_PATH:{filename}"