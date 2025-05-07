Here's the context: I have the same table from two different databases (one database for UAT environment, one for PROD). These tables are queryable through AWS Athena. My goal is to compile a report comparing the two tables' contents. You can assume they have the same table schema and columns, I am interested in knowing a few things from the table, assume the columns that make up the key of the table are provided as a list of strings called `key_columns`:
1) A row-level comparison between the two tables, more details to follow
3) Summary Statistics per Column: For each non-key column, calculate how many rows have different values between UAT and PROD.

The entrypoint will take the following information:
1) The database of the first table (e.g. df_trusted_uat)
2) The name of the first table (e.g. mdm_security)
3) The database of the second table (e.g. df_trusted_prod)
4) The name of the second table (e.g. mdm_security)
5) A list of columns that make up the keys in both tables
6) The current date: When you are comparing, you will only be compiling results for the current date

This code will be done in PySpark, you can query both tables using `spark.sql()` using Athena syntax. Your first task is to verify that they actually do have the same schema (i.e. both tables have the same columns, and column types).

Then, we will proceed with the report comparing the two tables. I want this generated as a markdown file, so make it look nice. Here is my vision:

The primary markdown file will be a summary/overview of the report

This will have stuff like the name of the two tables, the current date, and the schema of the tables (they should have same schema at this point so you only need to display that once). 

There should be an overview of each statistic. For the row level comparison, the primary markdown file will state how many keys exist in the first table, how many keys exist in the second table, how many keys exist in the second table but are missing from the first table, and how many keys exist in the first table but are missing from the second table.

The row level comparison will also include hyperlinks to other markdown files (these files also need to be created alongside the primary one of course, and make sure the tables are formatted nicely so that the columns line up, i want it to look AMAZING):
- There will be a link to a markdown file that will show pairs of rows, where the rows share the same key but have different values in one or more of the non-key columns. The columns that differ will be in bold.
- For "how many keys exist in the second table but are missing from the first table", there should be a hyperlink to another markdown file that contains all the rows in the second table that have keys missing from the first table.
- For "how many keys exist in the first table but are missing from the second table", there should be a hyperlink to another markdown file that contains all the rows in the first table that have keys missing from the second table.

─────────────────────────────────────────────
─────────────────────────────────────────────
─────────────────────────────────────────────

Okay, here's a PySpark script that implements the table comparison and markdown report generation as you've described.

**Key Features:**

1.  **Schema Verification:** Checks if both tables have identical column names, types, and order. Reports mismatches.
2.  **Date Filtering:** Filters data based on `current_date_str` and `date_partition_column`. If `date_partition_column` is empty or `None`, it processes the entire table.
3.  **Row-Level Comparison:**
    *   Identifies keys present only in the first table.
    *   Identifies keys present only in the second table.
    *   Identifies rows with common keys but differing values in non-key columns.
4.  **Summary Statistics:** For each non-key column, counts rows with differing values between the two tables (among common keys).
5.  **Markdown Report Generation:**
    *   A `summary_report.md` with overview, schema, counts, links to detailed reports, and column statistics.
    *   `keys_in_<table1>_missing_from_<table2>.md`: Lists rows from table 1 whose keys are not in table 2.
    *   `keys_in_<table2>_missing_from_<table1>.md`: Lists rows from table 2 whose keys are not in table 1.
    *   `rows_with_discrepancies.md`: Shows data for common keys where non-key columns differ. Differing values are **bolded**.
6.  **Error Handling:** Basic checks for table accessibility, schema issues, and empty key columns.
7.  **PySpark & Athena:** Uses `spark.sql()` for querying, compatible with Athena setups via AWS Glue Data Catalog.

```python
import pyspark.sql.functions as F
from pyspark.sql import SparkSession
import os

# Helper function to convert a DataFrame to a Markdown table string
def dataframe_to_markdown(df_to_convert, all_columns_ordered):
    """Converts a Spark DataFrame to a Markdown table string, ensuring column order."""
    if df_to_convert.isEmpty():
        return "No data to display.\n"

    # Ensure we display columns in the original table order
    columns_to_display = [col for col in all_columns_ordered if col in df_to_convert.columns]
    if not columns_to_display: # Should not happen if df_to_convert has data
        return "No columns to display.\n"

    header = "| " + " | ".join(columns_to_display) + " |"
    separator = "| " + " | ".join(["---"] * len(columns_to_display)) + " |"
    
    # Collect data. For reports requiring "all rows", this is necessary.
    # Be mindful of memory for extremely large discrepancy sets.
    data_rows = df_to_convert.select(columns_to_display).collect() 
    if not data_rows:
        return "No data to display.\n"

    body_rows = []
    for row in data_rows:
        row_values = []
        for col_name in columns_to_display:
            val = row[col_name]
            # Ensure consistent string representation, especially for None or special chars
            if val is None:
                row_values.append("") # Represent None as empty string in Markdown
            else:
                # Basic escaping for pipe characters in cell content
                row_values.append(str(val).replace("|", "\\|"))
        body_rows.append("| " + " | ".join(row_values) + " |")
    
    return "\n".join([header, separator] + body_rows) + "\n"

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
    Compares two Athena tables and generates a markdown report.
    """
    
    os.makedirs(output_dir, exist_ok=True)

    report_summary_file = os.path.join(output_dir, "summary_report.md")
    discrepancies_file = os.path.join(output_dir, "rows_with_discrepancies.md")
    keys_missing_from_table2_file = os.path.join(output_dir, f"keys_in_{table1_name}_missing_from_{table2_name}.md")
    keys_missing_from_table1_file = os.path.join(output_dir, f"keys_in_{table2_name}_missing_from_{table1_name}.md")

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
            if field1.dataType.simpleString() != field2.dataType.simpleString(): # Compare simple string representation
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
    non_key_columns = [col for col in all_columns_ordered if col not in key_columns]

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
    if non_key_columns:
        discrepancy_condition = F.lit(False)
        for col_name in non_key_columns:
            discrepancy_condition = discrepancy_condition | \
                (F.col(f"t1.{col_name}").eqNullSafe(F.col(f"t2.{col_name}")) == False)
        
        select_expr_discrepancies = [F.col(f"t1.{k_col}").alias(k_col) for k_col in key_columns]
        for nk_col in non_key_columns:
            select_expr_discrepancies.append(F.col(f"t1.{nk_col}").alias(f"{nk_col}_t1"))
            select_expr_discrepancies.append(F.col(f"t2.{nk_col}").alias(f"{nk_col}_t2"))

        data_discrepancies_df = common_keys_df.filter(discrepancy_condition)\
                                              .select(select_expr_discrepancies)
        data_discrepancies_df.cache()
        num_rows_with_discrepancies = data_discrepancies_df.count()
    else: # No non-key columns, so no data discrepancies possible.
        # Create an empty DataFrame with a schema that discrepancy reporting logic might expect (though it's guarded)
        # For this case, num_rows_with_discrepancies remains 0.
        # The schema for data_discrepancies_df is effectively: key_cols + nk_col1_t1, nk_col1_t2 ...
        # If non_key_columns is empty, it only has key_cols.
        # We don't need to create an empty data_discrepancies_df if it's not used.
        # The `if non_key_columns:` block for markdown generation will handle this.
        pass


    print("Calculating summary statistics per column...")
    column_summary_stats = []
    if non_key_columns and num_common_keys > 0 : # Only calculate if there are non-key columns and common keys
        for col_name in non_key_columns:
            mismatch_count = common_keys_df.filter(
                F.col(f"t1.{col_name}").eqNullSafe(F.col(f"t2.{col_name}")) == False
            ).count()
            column_summary_stats.append({'column_name': col_name, 'mismatched_rows': mismatch_count})
    
    print("Generating markdown reports...")

    with open(keys_missing_from_table2_file, "w", encoding="utf-8") as f:
        f.write(f"# Rows from `{table1_name}` with Keys Missing in `{table2_name}`\n\n")
        f.write(f"These rows exist in `{db1_name}.{table1_name}` but their keys are not found in `{db2_name}.{table2_name}` for the comparison date criteria.\n\n")
        if num_keys_only_in_table1 > 0:
            f.write(dataframe_to_markdown(rows_only_in_table1_df, all_columns_ordered))
        else:
            f.write(f"No keys found only in `{table1_name}`.\n")

    with open(keys_missing_from_table1_file, "w", encoding="utf-8") as f:
        f.write(f"# Rows from `{table2_name}` with Keys Missing in `{table1_name}`\n\n")
        f.write(f"These rows exist in `{db2_name}.{table2_name}` but their keys are not found in `{db1_name}.{table1_name}` for the comparison date criteria.\n\n")
        if num_keys_only_in_table2 > 0:
            f.write(dataframe_to_markdown(rows_only_in_table2_df, all_columns_ordered))
        else:
            f.write(f"No keys found only in `{table2_name}`.\n")

    discrepancy_md_content_parts = [f"# Data Discrepancies for Rows with Matching Keys\n\n"]
    discrepancy_md_content_parts.append(f"Comparison between `{db1_name}.{table1_name}` (T1) and `{db2_name}.{table2_name}` (T2) for the comparison date criteria.\n\n")
    if num_rows_with_discrepancies > 0 and non_key_columns:
        discrepancy_rows_collected = data_discrepancies_df.collect()
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

            for k_col in key_columns:
                val = row[k_col]
                str_val = str(val).replace("|", "\\|") if val is not None else ""
                current_table_rows_md.append(f"| {k_col} | {str_val} | {str_val} |\n")

            for nk_col in non_key_columns:
                val_t1, val_t2 = row[f"{nk_col}_t1"], row[f"{nk_col}_t2"]
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
    
    with open(discrepancies_file, "w", encoding="utf-8") as f:
        f.write("".join(discrepancy_md_content_parts))

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
    keys_fn1 = os.path.basename(keys_missing_from_table1_file)
    summary_md_parts.append(f"- Key sets in **`{table2_name}` (T2)** but missing from **`{table1_name}` (T1)**: {num_keys_only_in_table2} ([View Details]({keys_fn1}))\n")
    keys_fn2 = os.path.basename(keys_missing_from_table2_file)
    summary_md_parts.append(f"- Key sets in **`{table1_name}` (T1)** but missing from **`{table2_name}` (T2)**: {num_keys_only_in_table1} ([View Details]({keys_fn2}))\n")
    disc_fn = os.path.basename(discrepancies_file)
    if non_key_columns:
        summary_md_parts.append(f"- Rows with matching keys but different non-key values: {num_rows_with_discrepancies} ([View Details]({disc_fn}))\n\n")
    else:
        summary_md_parts.append(f"- Rows with matching keys but different non-key values: N/A (No non-key columns for comparison)\n\n")

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
        elif num_common_keys > 0: # Has common keys but stats list is empty (e.g. no diffs)
             for nk_col in non_key_columns: # Show all non-key columns with 0 diffs
                summary_md_parts.append(f"| {nk_col} | 0 |\n")
        else: # No common keys
             summary_md_parts.append("| N/A | N/A |\n")

    else: # No non-key columns
        summary_md_parts.append("## Summary Statistics per Non-Key Column\n\n")
        summary_md_parts.append("No non-key columns to provide statistics for.\n")

    with open(report_summary_file, "w", encoding="utf-8") as f:
        f.write("".join(summary_md_parts))

    print(f"Comparison complete. Reports generated in '{output_dir}'.")

    df1.unpersist()
    df2.unpersist()
    rows_only_in_table1_df.unpersist()
    rows_only_in_table2_df.unpersist()
    common_keys_df.unpersist()
    if non_key_columns and num_rows_with_discrepancies > 0 : # Check if DF was created and cached
        data_discrepancies_df.unpersist()


if __name__ == '__main__':
    spark = SparkSession.builder \
        .appName("AthenaTableComparison") \
        .enableHiveSupport() \
        .config("spark.sql.warehouse.dir", "spark-warehouse") # For local saveAsTable
        .getOrCreate()
    
    # Example: Creating dummy tables for a local test run
    spark.sql("CREATE DATABASE IF NOT EXISTS test_db_local")
    
    data1 = [ (1, "A", "val_X1", 100, "2023-01-01"), (1, "B", "val_Y1", 200, "2023-01-01"), 
              (2, "C", "val_Z1", 300, "2023-01-01"), (3, "D", "val_W1", 400, "2023-01-01"),
              (5, "E", "val_V1|pipe", 500, "2023-01-02"), (6, "G", None, 600, "2023-01-01") ] # Added pipe and None
    columns = ["id1", "id2", "value_col1", "value_col2", "date_col"]
    df_uat_src = spark.createDataFrame(data1, columns)
    df_uat_src.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/mdm_test_uat").saveAsTable("test_db_local.mdm_test_uat")

    data2 = [ (1, "A", "val_X2", 100, "2023-01-01"), (1, "B", "val_Y1", 201, "2023-01-01"),
              (3, "D", "val_W1", 400, "2023-01-01"), (4, "F", "val_Q2", 600, "2023-01-01"),
              (6, "G", "not_none", 600, "2023-01-01") ] # Changed for key 6
    df_prod_src = spark.createDataFrame(data2, columns)
    df_prod_src.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/mdm_test_prod").saveAsTable("test_db_local.mdm_test_prod")
    
    print("Dummy tables created for local testing.")
    
    compare_athena_tables(
        spark=spark, db1_name="test_db_local", table1_name="mdm_test_uat",
        db2_name="test_db_local", table2_name="mdm_test_prod",
        key_columns=["id1", "id2"], current_date_str="2023-01-01",
        date_partition_column="date_col", output_dir="my_comparison_report_output"
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
        date_partition_column="date_col", output_dir="my_comparison_report_schemamismatch"
    )
    
    # Test no non-key columns
    data_key_only = [(1, "A", "2023-01-01"), (2, "B", "2023-01-01")]
    key_only_cols = ["id1", "id2", "date_col"] # All displayable columns are keys or date_col
    df_key_only_uat = spark.createDataFrame(data_key_only, key_only_cols)
    df_key_only_uat.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/key_only_uat").saveAsTable("test_db_local.key_only_uat")
    data_key_only2 = [(1, "A", "2023-01-01"), (3, "C", "2023-01-01")]
    df_key_only_prod = spark.createDataFrame(data_key_only2, key_only_cols)
    df_key_only_prod.write.mode("overwrite").option("path", "./spark-warehouse/test_db_local/key_only_prod").saveAsTable("test_db_local.key_only_prod")
    print("\n--- Running test for no non-key columns (value_col1, value_col2 are key_columns here) ---")
    compare_athena_tables(
        spark=spark, db1_name="test_db_local", table1_name="key_only_uat",
        db2_name="test_db_local", table2_name="key_only_prod",
        key_columns=["id1", "id2"], # Non-key columns will be empty after removing date_col
        current_date_str="2023-01-01", date_partition_column="date_col",
        output_dir="my_comparison_report_nononkeycols"
    )

    spark.stop()

```
