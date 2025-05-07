Okay, I've updated the script to generate Excel files (`.xlsx`) for the detailed row-level comparisons, in addition to the markdown files.

**Changes Made:**

1.  **New Dependencies:** The script now uses `pandas` and `openpyxl`. You'll need to ensure these are installed in your PySpark environment (e.g., `pip install pandas openpyxl`).
2.  **`spark_df_to_excel` Helper Function:** A new helper function is added to convert a Spark DataFrame to a Pandas DataFrame and then save it to an Excel file.
3.  **Excel File Generation:**
    *   `keys_in_<table1>_missing_from_<table2>.xlsx`: Contains rows from table 1 not in table 2.
    *   `keys_in_<table2>_missing_from_<table1>.xlsx`: Contains rows from table 2 not in table 1.
    *   `rows_with_discrepancies.xlsx`: Contains rows with common keys but different non-key column values. The format is: key columns, then `non_key_col1_t1`, `non_key_col1_t2`, `non_key_col2_t1`, `non_key_col2_t2`, etc.
4.  **Updated Summary Markdown:** The `summary_report.md` now includes links to download these Excel files alongside the links to the detailed markdown reports.
5.  **Error Handling:** Basic error handling for Excel writing is included.
6.  **Memory Note:** Converting large Spark DataFrames to Pandas DataFrames (`.toPandas()`) collects all data to the driver node. If your "missing keys" or "discrepancy" datasets are extremely large, this could lead to memory issues on the driver. This was already a consideration for the `.collect()` in markdown generation, but it's worth reiterating for Excel.

Here's the updated code:

```python
import pyspark.sql.functions as F
from pyspark.sql import SparkSession
import os
import pandas as pd # Added for Excel export

# Helper function to convert a DataFrame to a Markdown table string
def dataframe_to_markdown(df_to_convert, all_columns_ordered):
    """Converts a Spark DataFrame to a Markdown table string, ensuring column order."""
    if df_to_convert.isEmpty():
        return "No data to display.\n"

    columns_to_display = [col for col in all_columns_ordered if col in df_to_convert.columns]
    if not columns_to_display:
        return "No columns to display.\n"

    header = "| " + " | ".join(columns_to_display) + " |"
    separator = "| " + " | ".join(["---"] * len(columns_to_display)) + " |"
    
    data_rows = df_to_convert.select(columns_to_display).collect() 
    if not data_rows:
        return "No data to display.\n"

    body_rows = []
    for row in data_rows:
        row_values = []
        for col_name in columns_to_display:
            val = row[col_name]
            if val is None:
                row_values.append("")
            else:
                row_values.append(str(val).replace("|", "\\|"))
        body_rows.append("| " + " | ".join(row_values) + " |")
    
    return "\n".join([header, separator] + body_rows) + "\n"

# Helper function to write Spark DF to Excel
def spark_df_to_excel(spark_df, excel_path, sheet_name="Data", all_columns_ordered=None):
    """Converts a Spark DataFrame to a Pandas DataFrame and saves it to an Excel file."""
    if spark_df.isEmpty():
        print(f"DataFrame is empty, not writing Excel file: {excel_path}")
        # Create an empty Excel file with headers if columns are known
        if all_columns_ordered:
            try:
                empty_pandas_df = pd.DataFrame(columns=all_columns_ordered)
                empty_pandas_df.to_excel(excel_path, sheet_name=sheet_name, index=False, engine='openpyxl')
                print(f"Wrote empty Excel file with headers to {excel_path}")
            except Exception as e:
                print(f"Error writing empty Excel file {excel_path}: {e}")
        return

    try:
        # Select columns in specific order if provided, otherwise use DataFrame's order
        if all_columns_ordered:
            # Ensure all_columns_ordered are actually in spark_df
            cols_to_select = [c for c in all_columns_ordered if c in spark_df.columns]
            if not cols_to_select and not spark_df.columns: # truly empty schema
                 pandas_df = pd.DataFrame()
            elif not cols_to_select and spark_df.columns: # mismatch
                 print(f"Warning: Columns for Excel export {all_columns_ordered} not found in DataFrame columns {spark_df.columns}. Using DF columns for {excel_path}.")
                 pandas_df = spark_df.toPandas()
            else:
                 pandas_df = spark_df.select(cols_to_select).toPandas()
        else:
            pandas_df = spark_df.toPandas()

        pandas_df.to_excel(excel_path, sheet_name=sheet_name, index=False, engine='openpyxl')
        print(f"Successfully wrote data to {excel_path}")
    except Exception as e:
        print(f"Error writing Spark DataFrame to Excel file {excel_path}: {e}")

# Main comparison function
def compare_athena_tables(
    spark: SparkSession,
    db1_name: str,
    table1_name: str,
    db2_name: str,
    table2_name: str,
    key_columns: list[str],
    current_date_str: str,
    date_partition_column: str, 
    output_dir: str = "comparison_report"
):
    """
    Compares two Athena tables and generates a markdown report and Excel files.
    """
    
    os.makedirs(output_dir, exist_ok=True)

    report_summary_file = os.path.join(output_dir, "summary_report.md")
    
    # Define base names for detailed reports
    base_name_discrepancies = "rows_with_discrepancies"
    base_name_keys_missing_from_t2 = f"keys_in_{table1_name}_missing_from_{table2_name}"
    base_name_keys_missing_from_t1 = f"keys_in_{table2_name}_missing_from_{table1_name}"

    # Markdown file paths
    discrepancies_md_file = os.path.join(output_dir, f"{base_name_discrepancies}.md")
    keys_missing_from_table2_md_file = os.path.join(output_dir, f"{base_name_keys_missing_from_t2}.md")
    keys_missing_from_table1_md_file = os.path.join(output_dir, f"{base_name_keys_missing_from_t1}.md")

    # Excel file paths
    discrepancies_excel_file = os.path.join(output_dir, f"{base_name_discrepancies}.xlsx")
    keys_missing_from_table2_excel_file = os.path.join(output_dir, f"{base_name_keys_missing_from_t2}.xlsx")
    keys_missing_from_table1_excel_file = os.path.join(output_dir, f"{base_name_keys_missing_from_t1}.xlsx")

    fq_table1_name = f"{db1_name}.{table1_name}"
    fq_table2_name = f"{db2_name}.{table2_name}"

    if not key_columns:
        error_msg = "Error: key_columns list cannot be empty."
        print(error_msg)
        with open(report_summary_file, "w", encoding="utf-8") as f:
            f.write(f"# Table Comparison Report for {table1_name} vs {table2_name}\n\n")
            f.write(f"Date of Comparison: {current_date_str}\n\n")
            f.write("## Configuration Error\n\n")
            f.write(f"```\n{error_msg}\n```\n")
        return

    try:
        schema1 = spark.table(fq_table1_name).schema
        schema2 = spark.table(fq_table2_name).schema
    except Exception as e:
        error_msg = f"Error accessing table schemas. Ensure tables exist and are accessible.\nTable 1: {fq_table1_name}\nTable 2: {fq_table2_name}\nError: {e}"
        print(error_msg)
        with open(report_summary_file, "w", encoding="utf-8") as f:
            f.write(f"# Table Comparison Report for {table1_name} vs {table2_name}\n\n")
            f.write(f"Date of Comparison: {current_date_str}\n\n")
            f.write("## Schema Verification Failed\n\n")
            f.write(f"```\n{error_msg}\n```\n")
        return

    schema_match = True
    schema_mismatch_reasons = []
    if len(schema1.fields) != len(schema2.fields):
        schema_match = False
        schema_mismatch_reasons.append(f"Different number of columns: Table 1 ({table1_name}) has {len(schema1.fields)}, Table 2 ({table2_name}) has {len(schema2.fields)}.")
    else:
        for i in range(len(schema1.fields)):
            field1, field2 = schema1.fields[i], schema2.fields[i]
            if field1.name != field2.name:
                schema_match = False
                schema_mismatch_reasons.append(f"Column name mismatch at index {i}: '{field1.name}' (Table 1) vs '{field2.name}' (Table 2).")
            if field1.dataType.simpleString() != field2.dataType.simpleString():
                schema_match = False
                schema_mismatch_reasons.append(f"Column type mismatch for column '{field1.name}': {field1.dataType.simpleString()} (Table 1) vs {field2.dataType.simpleString()} (Table 2).")
    
    schema_md_parts = ["### Table Schema\n"]
    if schema_match:
        schema_md_parts.append(f"Tables `{table1_name}` and `{table2_name}` have identical schemas:\n")
        schema_md_parts.append("| Column Name | Data Type |")
        schema_md_parts.append("|---|---|")
        for field in schema1.fields:
            schema_md_parts.append(f"| {field.name} | {field.dataType.simpleString()} |")
    else:
        schema_md_parts.append("Schema Mismatch Found:\n")
        for reason in schema_mismatch_reasons:
            schema_md_parts.append(f"- {reason}\n")
    schema_markdown = "\n".join(schema_md_parts) + "\n\n"

    if not schema_match:
        print("Schema verification failed. Aborting comparison.")
        with open(report_summary_file, "w", encoding="utf-8") as f:
            f.write(f"# Table Comparison Report for {table1_name} vs {table2_name}\n\n")
            f.write(f"Date of Comparison: {current_date_str}\n\n")
            f.write(schema_markdown)
        return

    all_columns_ordered = [field.name for field in schema1.fields]
    non_key_columns = [col for col in all_columns_ordered if col not in key_columns and col != date_partition_column]

    print(f"Loading data for date: {current_date_str} (filter column: {date_partition_column if date_partition_column else 'None'})...")
    def load_table_data(db_name, tbl_name, cols_to_select):
        query = f"SELECT {', '.join(cols_to_select)} FROM {db_name}.{tbl_name}"
        if date_partition_column and current_date_str:
            query += f" WHERE {date_partition_column} = '{current_date_str}'"
        return spark.sql(query)

    df1 = load_table_data(db1_name, table1_name, all_columns_ordered).alias("t1")
    df2 = load_table_data(db2_name, table2_name, all_columns_ordered).alias("t2")
    
    df1.cache()
    df2.cache()

    print("Performing row-level comparison...")
    join_expr = F.lit(True)
    for col_name in key_columns:
        join_expr = join_expr & (F.col(f"t1.{col_name}") == F.col(f"t2.{col_name}"))
    
    joined_df = df1.join(df2, join_expr, "full_outer")
    
    condition_only_in_t1 = F.col(f"t2.{key_columns[0]}").isNull()
    rows_only_in_table1_df = joined_df.filter(condition_only_in_t1)\
                                     .select([F.col(f"t1.{c}").alias(c) for c in all_columns_ordered])
    rows_only_in_table1_df.cache()
    num_keys_only_in_table1 = rows_only_in_table1_df.count()

    condition_only_in_t2 = F.col(f"t1.{key_columns[0]}").isNull()
    rows_only_in_table2_df = joined_df.filter(condition_only_in_t2)\
                                     .select([F.col(f"t2.{c}").alias(c) for c in all_columns_ordered])
    rows_only_in_table2_df.cache()
    num_keys_only_in_table2 = rows_only_in_table2_df.count()

    condition_common_keys = F.col(f"t1.{key_columns[0]}").isNotNull() & F.col(f"t2.{key_columns[0]}").isNotNull()
    common_keys_df = joined_df.filter(condition_common_keys).cache()
    num_common_keys = common_keys_df.count()

    total_distinct_keys_table1 = num_keys_only_in_table1 + num_common_keys
    total_distinct_keys_table2 = num_keys_only_in_table2 + num_common_keys
    
    num_rows_with_discrepancies = 0
    data_discrepancies_df_for_excel = None # Initialize
    if non_key_columns:
        discrepancy_condition = F.lit(False)
        for col_name in non_key_columns:
            discrepancy_condition = discrepancy_condition | \
                (F.col(f"t1.{col_name}").eqNullSafe(F.col(f"t2.{col_name}")) == False)
        
        select_expr_discrepancies = [F.col(f"t1.{k_col}").alias(k_col) for k_col in key_columns]
        excel_ordered_cols_discrepancy = list(key_columns) # Start with key columns
        for nk_col in non_key_columns:
            select_expr_discrepancies.append(F.col(f"t1.{nk_col}").alias(f"{nk_col}_{table1_name}")) # More descriptive suffix
            select_expr_discrepancies.append(F.col(f"t2.{nk_col}").alias(f"{nk_col}_{table2_name}"))
            excel_ordered_cols_discrepancy.append(f"{nk_col}_{table1_name}")
            excel_ordered_cols_discrepancy.append(f"{nk_col}_{table2_name}")

        data_discrepancies_df_for_excel = common_keys_df.filter(discrepancy_condition)\
                                              .select(select_expr_discrepancies)
        data_discrepancies_df_for_excel.cache()
        num_rows_with_discrepancies = data_discrepancies_df_for_excel.count()
    else:
        # Create an empty schema DataFrame if no non-key columns for Excel consistency
        schema_for_empty_discrepancy_df = [F.col(f"t1.{k_col}").alias(k_col) for k_col in key_columns]
        # This part might need adjustment if spark.createDataFrame needs a schema argument differently
        # For now, assume it will be empty and handled by spark_df_to_excel
        if common_keys_df.count() > 0: # Only try to create if common_keys_df is not empty
            data_discrepancies_df_for_excel = common_keys_df.limit(0).select(schema_for_empty_discrepancy_df)
        else: # If common_keys_df is empty, just create an empty DF
            data_discrepancies_df_for_excel = spark.createDataFrame([], schema=spark.table(fq_table1_name).select(key_columns).schema)
        data_discrepancies_df_for_excel.cache()
        excel_ordered_cols_discrepancy = list(key_columns) # For empty Excel header

    print("Calculating summary statistics per column...")
    column_summary_stats = []
    if non_key_columns and num_common_keys > 0 :
        for col_name in non_key_columns:
            mismatch_count = common_keys_df.filter(
                F.col(f"t1.{col_name}").eqNullSafe(F.col(f"t2.{col_name}")) == False
            ).count()
            column_summary_stats.append({'column_name': col_name, 'mismatched_rows': mismatch_count})
    
    print("Generating reports (Markdown and Excel)...")

    # Keys in Table 1, Missing from Table 2
    with open(keys_missing_from_table2_md_file, "w", encoding="utf-8") as f:
        f.write(f"# Rows from `{table1_name}` with Keys Missing in `{table2_name}`\n\n")
        f.write(f"These rows exist in `{db1_name}.{table1_name}` but their keys are not found in `{db2_name}.{table2_name}` for the comparison date criteria.\n\n")
        if num_keys_only_in_table1 > 0:
            f.write(dataframe_to_markdown(rows_only_in_table1_df, all_columns_ordered))
        else:
            f.write(f"No keys found only in `{table1_name}`.\n")
    spark_df_to_excel(rows_only_in_table1_df, keys_missing_from_table2_excel_file, 
                      sheet_name=f"In_{table1_name}_NotIn_{table2_name}", all_columns_ordered=all_columns_ordered)

    # Keys in Table 2, Missing from Table 1
    with open(keys_missing_from_table1_md_file, "w", encoding="utf-8") as f:
        f.write(f"# Rows from `{table2_name}` with Keys Missing in `{table1_name}`\n\n")
        f.write(f"These rows exist in `{db2_name}.{table2_name}` but their keys are not found in `{db1_name}.{table1_name}` for the comparison date criteria.\n\n")
        if num_keys_only_in_table2 > 0:
            f.write(dataframe_to_markdown(rows_only_in_table2_df, all_columns_ordered))
        else:
            f.write(f"No keys found only in `{table2_name}`.\n")
    spark_df_to_excel(rows_only_in_table2_df, keys_missing_from_table1_excel_file, 
                      sheet_name=f"In_{table2_name}_NotIn_{table1_name}", all_columns_ordered=all_columns_ordered)

    # Data Discrepancies for common keys
    # Excel for discrepancies (using the _for_excel DF)
    spark_df_to_excel(data_discrepancies_df_for_excel, discrepancies_excel_file,
                      sheet_name="Discrepancies", all_columns_ordered=excel_ordered_cols_discrepancy)
    
    # Markdown for discrepancies (more complex formatting)
    discrepancy_md_content_parts = [f"# Data Discrepancies for Rows with Matching Keys\n\n"]
    discrepancy_md_content_parts.append(f"Comparison between `{db1_name}.{table1_name}` (T1) and `{db2_name}.{table2_name}` (T2) for the comparison date criteria.\n\n")
    if num_rows_with_discrepancies > 0 and non_key_columns:
        # For markdown, we re-use data_discrepancies_df_for_excel (which has t1/t2 suffixed cols)
        # Or, if preferred, re-fetch from common_keys_df. Let's use the _for_excel one as it's cached.
        discrepancy_rows_collected = data_discrepancies_df_for_excel.collect() # This already has t1/t2 suffixed non-key cols
        
        for row_idx, row in enumerate(discrepancy_rows_collected):
            key_values_str_list = []
            for k_col in key_columns:
                val = row[k_col]
                key_values_str_list.append(f"{k_col}: {str(val).replace('|', '\\|') if val is not None else ''}")
            key_values_str = ", ".join(key_values_str_list)
            
            discrepancy_md_content_parts.append(f"## Discrepancy Entry {row_idx + 1} (Key: {key_values_str})\n")
            
            table_header = f"| Column | Value from `{table1_name}` (T1) | Value from `{table2_name}` (T2) |\n"
            table_separator = "|---|---|---|\n"
            current_table_rows_md = []

            for k_col in key_columns: # Key columns are same
                val = row[k_col]
                str_val = str(val).replace("|", "\\|") if val is not None else ""
                current_table_rows_md.append(f"| {k_col} | {str_val} | {str_val} |\n")

            for nk_col in non_key_columns:
                val_t1 = row[f"{nk_col}_{table1_name}"] # Using suffixed column names
                val_t2 = row[f"{nk_col}_{table2_name}"]
                str_val_t1 = str(val_t1).replace("|", "\\|") if val_t1 is not None else ""
                str_val_t2 = str(val_t2).replace("|", "\\|") if val_t2 is not None else ""
                
                is_different = False
                if val_t1 is None and val_t2 is not None: is_different = True
                elif val_t1 is not None and val_t2 is None: is_different = True
                elif val_t1 is not None and val_t2 is not None and val_t1 != val_t2: is_different = True
                
                if is_different:
                    current_table_rows_md.append(f"| {nk_col} | **{str_val_t1}** | **{str_val_t2}** |\n")
                else:
                    current_table_rows_md.append(f"| {nk_col} | {str_val_t1} | {str_val_t2} |\n")
            
            discrepancy_md_content_parts.append(table_header + table_separator + "".join(current_table_rows_md) + "\n")
    elif not non_key_columns:
        discrepancy_md_content_parts.append("No non-key columns were specified to compare for discrepancies.\n")
    else:
        discrepancy_md_content_parts.append("No data discrepancies found for rows with matching keys.\n")
    
    with open(discrepancies_md_file, "w", encoding="utf-8") as f:
        f.write("".join(discrepancy_md_content_parts))

    # Summary Markdown
    summary_md_parts = [f"# Table Comparison Report: `{table1_name}` vs `{table2_name}`\n\n"]
    summary_md_parts.append(f"**Date of Comparison:** {current_date_str}\n")
    if date_partition_column and current_date_str:
        summary_md_parts.append(f"**Data filtered by:** `{date_partition_column} = '{current_date_str}'`\n")
    else:
        summary_md_parts.append(f"**Data filtered by:** No date filter applied (full tables compared)\n")
    summary_md_parts.append(f"**Table 1 (T1):** `{db1_name}.{table1_name}`\n")
    summary_md_parts.append(f"**Table 2 (T2):** `{db2_name}.{table2_name}`\n")
    summary_md_parts.append(f"**Key Columns:** `{', '.join(key_columns)}`\n\n")
    summary_md_parts.append(schema_markdown)
    summary_md_parts.append("## Row-Level Comparison Summary\n\n")
    summary_md_parts.append(f"- Total distinct key sets in **`{table1_name}` (T1)**: {total_distinct_keys_table1}\n")
    summary_md_parts.append(f"- Total distinct key sets in **`{table2_name}` (T2)**: {total_distinct_keys_table2}\n")
    
    # Links to detailed reports (MD and Excel)
    md_fn_missing_t1 = os.path.basename(keys_missing_from_table1_md_file)
    excel_fn_missing_t1 = os.path.basename(keys_missing_from_table1_excel_file)
    summary_md_parts.append(f"- Key sets in **`{table2_name}` (T2)** but missing from **`{table1_name}` (T1)**: {num_keys_only_in_table2} ([View MD]({md_fn_missing_t1}) / [Download Excel]({excel_fn_missing_t1}))\n")
    
    md_fn_missing_t2 = os.path.basename(keys_missing_from_table2_md_file)
    excel_fn_missing_t2 = os.path.basename(keys_missing_from_table2_excel_file)
    summary_md_parts.append(f"- Key sets in **`{table1_name}` (T1)** but missing from **`{table2_name}` (T2)**: {num_keys_only_in_table1} ([View MD]({md_fn_missing_t2}) / [Download Excel]({excel_fn_missing_t2}))\n")
    
    md_fn_discrepancies = os.path.basename(discrepancies_md_file)
    excel_fn_discrepancies = os.path.basename(discrepancies_excel_file)
    if non_key_columns:
        summary_md_parts.append(f"- Rows with matching keys but different non-key values: {num_rows_with_discrepancies} ([View MD]({md_fn_discrepancies}) / [Download Excel]({excel_fn_discrepancies}))\n\n")
    else:
        summary_md_parts.append(f"- Rows with matching keys but different non-key values: N/A (No non-key columns for comparison) ([View MD]({md_fn_discrepancies}) / [Download Excel]({excel_fn_discrepancies}))\n\n")


    if non_key_columns:
        summary_md_parts.append("## Summary Statistics per Non-Key Column\n\n")
        if num_common_keys > 0:
             summary_md_parts.append(f"Based on {num_common_keys} common key set(s):\n")
        else:
            summary_md_parts.append(f"No common key sets found to compare non-key columns.\n")
        summary_md_parts.append("| Non-Key Column | Number of Rows with Different Values (T1 vs T2) |\n")
        summary_md_parts.append("|---|---|\n")
        if column_summary_stats:
            for stat in column_summary_stats:
                summary_md_parts.append(f"| {stat['column_name']} | {stat['mismatched_rows']} |\n")
        elif num_common_keys > 0:
             for nk_col in non_key_columns:
                summary_md_parts.append(f"| {nk_col} | 0 |\n")
        else:
             summary_md_parts.append("| N/A | N/A |\n")
    else:
        summary_md_parts.append("## Summary Statistics per Non-Key Column\n\n")
        summary_md_parts.append("No non-key columns to provide statistics for.\n")

    with open(report_summary_file, "w", encoding="utf-8") as f:
        f.write("".join(summary_md_parts))

    print(f"Comparison complete. Reports generated in '{output_dir}'.")

    # Unpersist DataFrames
    df1.unpersist()
    df2.unpersist()
    rows_only_in_table1_df.unpersist()
    rows_only_in_table2_df.unpersist()
    common_keys_df.unpersist()
    if data_discrepancies_df_for_excel: # Check if it was created
        data_discrepancies_df_for_excel.unpersist()


if __name__ == '__main__':
    spark = SparkSession.builder \
        .appName("AthenaTableComparison") \
        .enableHiveSupport() \
        .config("spark.sql.warehouse.dir", "spark-warehouse") 
        .getOrCreate()
    
    # Ensure pandas and openpyxl are installed for the example to run locally.
    # You might need to: pip install pandas openpyxl
    try:
        import pandas
        import openpyxl
    except ImportError:
        print("Please install pandas and openpyxl: pip install pandas openpyxl")
        spark.stop()
        exit()

    print("Creating dummy tables for local testing...")
    spark.sql("CREATE DATABASE IF NOT EXISTS test_db_local")
    
    data1 = [ (1, "A", "val_X1", 100, "2023-01-01"), (1, "B", "val_Y1", 200, "2023-01-01"), 
              (2, "C", "val_Z1", 300, "2023-01-01"), (3, "D", "val_W1", 400, "2023-01-01"),
              (5, "E", "val_V1|pipe", 500, "2023-01-02"), (6, "G", None, 600, "2023-01-01") ]
    columns = ["id1", "id2", "value_col1", "value_col2", "date_col"]
    df_uat_src = spark.createDataFrame(data1, columns)
    df_uat_src.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/mdm_test_uat").saveAsTable("test_db_local.mdm_test_uat")

    data2 = [ (1, "A", "val_X2", 100, "2023-01-01"), (1, "B", "val_Y1", 201, "2023-01-01"),
              (3, "D", "val_W1", 400, "2023-01-01"), (4, "F", "val_Q2", 600, "2023-01-01"),
              (6, "G", "not_none", 600, "2023-01-01") ]
    df_prod_src = spark.createDataFrame(data2, columns)
    df_prod_src.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/mdm_test_prod").saveAsTable("test_db_local.mdm_test_prod")
    
    print("Dummy tables created for local testing.")
    
    compare_athena_tables(
        spark=spark, db1_name="test_db_local", table1_name="mdm_test_uat",
        db2_name="test_db_local", table2_name="mdm_test_prod",
        key_columns=["id1", "id2"], current_date_str="2023-01-01",
        date_partition_column="date_col", output_dir="my_comparison_report_excel_output"
    )

    # Test schema mismatch
    data_schema_diff = [(1, "A", "val_X1", "extra_val", 100, "2023-01-01")]
    columns_schema_diff = ["id1", "id2", "value_col1", "extra_field", "value_col2", "date_col"]
    df_uat_schema_diff_src = spark.createDataFrame(data_schema_diff, columns_schema_diff)
    df_uat_schema_diff_src.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/mdm_test_uat_schemadiff").saveAsTable("test_db_local.mdm_test_uat_schemadiff")
    print("\n--- Running test for schema mismatch ---")
    compare_athena_tables(
        spark=spark, db1_name="test_db_local", table1_name="mdm_test_uat_schemadiff",
        db2_name="test_db_local", table2_name="mdm_test_prod",
        key_columns=["id1", "id2"], current_date_str="2023-01-01",
        date_partition_column="date_col", output_dir="my_comparison_report_schemamismatch_excel"
    )
    
    # Test no non-key columns
    data_key_only = [(1, "A", "2023-01-01"), (2, "B", "2023-01-01")]
    # Non-key columns will be empty after removing key_columns and date_partition_column
    key_only_cols = ["id1", "id2", "date_col"] 
    df_key_only_uat = spark.createDataFrame(data_key_only, key_only_cols)
    df_key_only_uat.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/key_only_uat").saveAsTable("test_db_local.key_only_uat")
    
    data_key_only2 = [(1, "A", "2023-01-01"), (3, "C", "2023-01-01")]
    df_key_only_prod = spark.createDataFrame(data_key_only2, key_only_cols)
    df_key_only_prod.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/key_only_prod").saveAsTable("test_db_local.key_only_prod")
    print("\n--- Running test for no non-key columns ---")
    compare_athena_tables(
        spark=spark, db1_name="test_db_local", table1_name="key_only_uat",
        db2_name="test_db_local", table2_name="key_only_prod",
        key_columns=["id1", "id2"], 
        current_date_str="2023-01-01", date_partition_column="date_col",
        output_dir="my_comparison_report_nononkeycols_excel"
    )

    spark.stop()
```
