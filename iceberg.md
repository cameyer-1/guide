
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

Parse through the pyiceberg documentation, if you understand everything, say yes:

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

Design a python project that does the following:
1) Users can define iceberg tables (with the absolutely necessary fields, ID numbers and all that should be done implicitly) and should be user-friendly. These definitions will be defined with YAML files
2) These yaml files can be ingested by this python project and will create a iceberg table in AWS such that it'll appear in AWS Glue and is query-able with AWS Athena
3) There will also be a python library that provides users with methods to do regular iceberg functions like insert/update/upsert/delete/read data
4) The project should be modular and easy expandable. Something you would expect from a senior principle staff engineer with years of experience designing projects

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

Okay, let's design a robust and extensible Python project for managing Iceberg tables defined via YAML, targeting AWS Glue and S3. This design emphasizes modularity, separation of concerns, and adherence to good engineering practices.

**Project Name:** `iceberg_table_manager` (or similar)

**Core Concepts:**

1.  **Declarative Definitions:** Users define the *desired state* of their tables in YAML.
2.  **Idempotent Operations:** Applying a YAML definition should result in the same table state, whether creating or updating (though updates are more complex and might be staged for future phases). The initial focus will be creation.
3.  **Abstraction:** Hide the complexities of PyIceberg field IDs, schema building, and catalog interactions behind simpler interfaces.
4.  **Pluggability:** While targeting AWS Glue initially, the design should allow for other catalogs or FileIOs in the future.

**Project Structure:**

```
iceberg_table_manager/
├── iceberg_table_manager/
│   ├── definitions/          # Handles YAML definition loading, validation, parsing
│   │   ├── __init__.py
│   │   ├── loader.py         # Loads YAML file content
│   │   ├── validator.py      # Validates YAML structure and basic types
│   │   ├── parser.py         # Parses validated YAML into internal Python objects
│   │   └── schemas/          # (Optional) JSON schemas for YAML validation
│   │       └── table_definition.v1.schema.json
│   │
│   ├── iceberg/              # Interfaces with PyIceberg
│   │   ├── __init__.py
│   │   ├── schema_builder.py # Builds PyIceberg Schema from parsed definition (handles IDs)
│   │   ├── catalog_manager.py# Manages catalog connections (initially Glue)
│   │   ├── table_creator.py  # Creates the table in the catalog
│   │   └── type_mapping.py   # Maps YAML types to PyIceberg/PyArrow types
│   │
│   ├── library/              # User-facing Python library for table operations
│   │   ├── __init__.py
│   │   ├── managed_table.py  # Class representing a managed Iceberg table
│   │   └── operations.py     # Functions like insert, read, etc. (could be methods on ManagedTable)
│   │
│   ├── cli/                  # Command-line interface (optional but recommended)
│   │   ├── __init__.py
│   │   ├── main.py           # Entry point (e.g., using Typer or Click)
│   │   └── commands.py       # CLI command implementations
│   │
│   ├── config/               # Configuration loading (wraps/uses PyIceberg config)
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── exceptions.py         # Custom exceptions
│   ├── __init__.py           # Expose main library functions/classes
│
├── examples/                 # Example YAML definitions
│   └── user_events.yaml
│
├── tests/                    # Unit and integration tests
│   ├── definitions/
│   ├── iceberg/
│   ├── library/
│   ├── cli/
│   └── fixtures/             # Test data, mock objects
│
├── pyproject.toml            # Project metadata, dependencies (using Poetry or similar)
├── README.md
├── .gitignore
└── .pyiceberg.yaml           # Default configuration for the project/tests
```

**Component Breakdown & Design Details:**

1.  **`definitions` Module:**
    *   `loader.py`: Uses `PyYAML` to load YAML files.
    *   `validator.py`:
        *   Uses `jsonschema` (if using JSON schema) or custom Python logic to validate the presence of required fields (`namespace`, `table_name`, `location`, `schema.columns`), data types, and allowed values (e.g., for partition transforms).
        *   Ensures column names are valid identifiers.
    *   `parser.py`: Converts the validated dictionary into more structured Pydantic models or dataclasses for easier handling downstream. This makes the internal representation explicit.

2.  **`iceberg` Module:**
    *   `type_mapping.py`: Defines dictionaries to map user-friendly YAML types (`string`, `long`, `timestamptz`, `map<string,int>`, `struct<a:int,b:string>`) to `pyiceberg.types` (and potentially `pyarrow.types` for validation during operations). Handles parsing complex types.
    *   `schema_builder.py`:
        *   **Crucial:** Takes the parsed definition (from `definitions.parser`).
        *   Iterates through columns defined in YAML.
        *   Maps YAML types to PyIceberg types using `type_mapping`.
        *   **Implicitly assigns unique, sequential `field_id`s** starting from 1 for top-level columns and recursively for nested types (structs, maps, lists). It needs to keep track of the next available ID.
        *   Builds the `pyiceberg.schema.Schema` object.
        *   Builds `pyiceberg.partitioning.PartitionSpec` by mapping source columns and YAML transforms (`day`, `bucket[N]`, `identity`, etc.) to PyIceberg transforms. Assigns `field_id`s (e.g., starting from 1000).
        *   Builds `pyiceberg.table.sorting.SortOrder` similarly, assigning `order_id` (usually starts at 0).
        *   Parses identifier fields for V2 tables used in upserts.
    *   `catalog_manager.py`:
        *   Uses `pyiceberg.catalog.load_catalog` to load the target catalog (initially configured for Glue, potentially reading catalog name from config or YAML).
        *   Handles catalog-related exceptions.
    *   `table_creator.py`:
        *   Takes the parsed definition, the built `Schema`, `PartitionSpec`, `SortOrder`.
        *   Gets the catalog instance from `catalog_manager`.
        *   Checks if the namespace exists, creates if not (`catalog.create_namespace`).
        *   Checks if the table exists. If it does, decide on behavior (fail, log, skip - initially fail or skip).
        *   Calls `catalog.create_table` with the generated schema, partition spec, sort order, location, and properties from the YAML.

3.  **`library` Module:**
    *   `managed_table.py`:
        *   `ManagedTable` class:
            *   `__init__`: Takes namespace, table name, and optionally a pre-loaded catalog instance. Loads the catalog if not provided. Loads the `pyiceberg.table.Table` object (`catalog.load_table`).
            *   Stores the loaded `pyiceberg_table` internally.
            *   Provides methods wrapping core PyIceberg table operations.
    *   `operations.py` (or methods within `ManagedTable`):
        *   `read(managed_table: ManagedTable, ...) -> pyarrow.Table`: Uses `managed_table.pyiceberg_table.scan(...).to_arrow()`.
        *   `insert(managed_table: ManagedTable, data: pyarrow.Table)`: Validates input `data` schema against table schema (optional but recommended). Calls `managed_table.pyiceberg_table.append(data)`.
        *   `overwrite(managed_table: ManagedTable, data: pyarrow.Table, ...)`: Calls `managed_table.pyiceberg_table.overwrite(data, ...)`.
        *   `upsert(managed_table: ManagedTable, data: pyarrow.Table)`: Requires identifier fields defined in the table. Calls `managed_table.pyiceberg_table.upsert(data)`. Ensure the table schema was created *with* identifier fields specified.
        *   `delete(managed_table: ManagedTable, row_filter: str)`: Calls `managed_table.pyiceberg_table.delete(row_filter)`.
        *   `get_schema(managed_table: ManagedTable) -> pyiceberg.Schema`: Returns `managed_table.pyiceberg_table.schema()`.
        *   `get_location(managed_table: ManagedTable) -> str`: Returns `managed_table.pyiceberg_table.location()`.

4.  **`cli` Module:**
    *   Uses `typer` or `click`.
    *   Command `create-from-yaml`:
        *   Takes `--yaml-path` argument.
        *   Uses `definitions.loader` -> `validator` -> `parser`.
        *   Uses `iceberg.schema_builder` to build Iceberg objects.
        *   Uses `iceberg.table_creator` to create the table.
        *   Provides clear success/error messages.

5.  **`config` Module:**
    *   Relies heavily on PyIceberg's built-in config loading (`.pyiceberg.yaml`, env vars).
    *   Might add functions to easily retrieve specific catalog configurations needed by the manager.
    *   Ensures necessary AWS credentials/region configuration for Glue/S3 is documented/handled (typically via standard AWS SDK env vars like `AWS_REGION`, `AWS_ACCESS_KEY_ID`, etc., which PyIceberg/boto3 pick up).

6.  **`exceptions.py`:**
    *   `DefinitionValidationError`, `SchemaBuildError`, `TableCreationError`, `TableOperationError`, etc.

**Example YAML (`examples/user_events.yaml`):**

```yaml
# Version for the definition format itself (optional but good practice)
definition_format_version: 1

# Target catalog name (defined in .pyiceberg.yaml or env vars)
# Optional: Can default to 'default' or be a CLI arg
catalog_name: aws_glue_prod

namespace: web_analytics
table_name: user_events

# Root location for the table data and metadata on S3
location: s3://my-data-lake-bucket/iceberg/web_analytics/user_events

# Optional: Table properties
properties:
  write.parquet.compression-codec: zstd
  # For Glue compatibility if needed
  # comment: "Table storing user interaction events."

schema:
  columns:
    - name: event_uuid       # Clear, descriptive names
      type: uuid            # User-friendly types mapped internally
      required: true        # Explicit nullability
      doc: "Unique identifier for each event record" # Documentation is good practice
    - name: user_id
      type: long
      required: true
      doc: "Identifier for the user"
    - name: event_timestamp
      type: timestamptz    # Timestamp with timezone awareness
      required: true
    - name: event_type
      type: string
      required: false     # Default to nullable if 'required' omitted
    - name: device_info
      type: struct<os:string, browser:string, version:string> # Nested struct
      required: false
    - name: properties
      type: map<string, string>  # Map type
      required: false
    - name: page_url
      type: string

# Optional: Define how the table is partitioned
partition_spec:
  - source_column: event_timestamp
    transform: day        # User-friendly transforms
    name: event_day       # Optional: Custom name for the partition field
  - source_column: event_type
    transform: identity   # Partition by raw event_type

# Optional: Define the sort order for writes
sort_order:
  - column: event_timestamp
    direction: asc        # asc or desc
    null_order: nulls_first # nulls_first or nulls_last
  - column: user_id
    direction: asc

# Optional: Required for V2 tables and upsert operations
identifier_fields:
  - event_uuid
```

**Key Design Principles Applied:**

*   **Single Responsibility Principle:** Each module/class has a focused purpose (loading, validation, schema building, table creation, operations).
*   **Dependency Inversion:** The core logic depends on abstractions (like a parsed definition object) rather than concrete file loading or specific catalog types directly where possible. `catalog_manager` abstracts catalog loading.
*   **Configuration Management:** Leverages PyIceberg's existing, flexible system.
*   **Testability:** Clear separation makes unit testing easier. Integration tests will be needed for catalog interactions.
*   **Extensibility:**
    *   Adding support for another catalog involves updating `catalog_manager` and potentially adding catalog-specific properties to the YAML/validation.
    *   Adding new YAML features (e.g., complex default values) involves updating the parser, validator, and potentially the schema builder.
    *   Adding new library operations is straightforward in the `library` module.

**How to Use (Conceptual):**

1.  **Configure AWS:** Ensure AWS credentials and region are configured (e.g., via environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`).
2.  **Configure PyIceberg:** Set up `.pyiceberg.yaml` to define the Glue catalog connection (`aws_glue_prod` in the example).
    ```yaml
    catalog:
      aws_glue_prod:
        type: glue
        # Potentially add warehouse, s3 configs if needed globally
        # Glue region might be inferred from AWS_REGION env var
        # Credentials often handled by boto3 automatically (env vars, profile, instance role)
    ```
3.  **Define Table:** Create `user_events.yaml`.
4.  **Create Table (CLI):** `iceberg-manager create-from-yaml --yaml-path examples/user_events.yaml`
5.  **Use Library:**
    ```python
    from iceberg_table_manager import load_managed_table
    import pyarrow as pa

    # Load the table interface
    managed_table = load_managed_table(namespace="web_analytics", table_name="user_events", catalog_name="aws_glue_prod")

    # Prepare data (matching the defined schema, respecting nullability)
    data_to_insert = pa.table({
        'event_uuid': pa.array(['...', '...'], type=pa.string()), # Assuming UUIDs as strings for Arrow
        'user_id': pa.array([123, 456], type=pa.int64()),
        'event_timestamp': pa.array([ ... ], type=pa.timestamp('us', tz='UTC')),
        'event_type': pa.array(['click', 'view'], type=pa.string()),
        'device_info': pa.array([{'os': 'macOS', 'browser': 'Chrome', 'version': '110'}, None], type=pa.struct([('os', pa.string()), ('browser', pa.string()), ('version', pa.string())])),
        'properties': pa.array([[{'key': 'source', 'value': 'ads'}], None], type=pa.map_(pa.string(), pa.string())),
        'page_url': pa.array(['/home', '/products'], type=pa.string())
    }, schema=managed_table.get_pyarrow_schema()) # Get Arrow schema from table

    # Insert data
    managed_table.insert(data_to_insert)

    # Read data
    df_arrow = managed_table.read(row_filter="user_id = 123")
    print(df_arrow)

    # Delete data
    managed_table.delete("event_type = 'spam'")
    ```

This design provides a solid foundation that meets the requirements and is built for future growth and maintenance.

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

Is there a way to define a primary key for the table? Like lets say two columns together form a primary key that uniquely identifies a row in the table. Does that work?

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

Yes, absolutely. While Apache Iceberg doesn't use the term "primary key" in the exact same way as a relational database (it doesn't automatically enforce uniqueness on simple appends), it has a mechanism specifically for uniquely identifying rows for operations like **upserts** and **equality deletes**. This is crucial for managing data at the row level in V2 tables.

This mechanism is the **`identifier_fields`** property in the table's metadata.

Here's how it works and how you'd integrate it into the designed project:

1.  **Iceberg Concept: `identifier_fields`**
    *   You specify one or more columns (by their field IDs) that logically identify a unique row within the table.
    *   This **requires the table to be format version 2 (V2)**. V1 tables do not support row-level operations or identifier fields.
    *   **Important Distinction:** Unlike an RDBMS primary key, `identifier_fields` **do not prevent** you from writing duplicate rows using a standard `append` operation. Their purpose is to allow operations like `upsert` to *find* existing rows based on these fields and decide whether to update them or insert a new row. Equality deletes also use these fields to find rows to remove.

2.  **Integrating into the YAML Definition:**
    You would add a top-level key to your YAML definition, listing the *names* of the columns that constitute the logical unique identifier.

    ```yaml
    # examples/user_events_with_pk.yaml
    definition_format_version: 1
    catalog_name: aws_glue_prod
    namespace: web_analytics
    table_name: user_events_v2

    location: s3://my-data-lake-bucket/iceberg/web_analytics/user_events_v2

    # Specify the table format version (REQUIRED for identifier_fields)
    properties:
      format-version: 2 # Set table to V2
      write.parquet.compression-codec: zstd
      # ... other properties

    schema:
      columns:
        - name: event_uuid
          type: uuid
          required: true
          doc: "Unique identifier for each event record"
        - name: session_id # Maybe part of a composite key?
          type: string
          required: true
          doc: "User session identifier"
        - name: user_id
          type: long
          required: true
        - name: event_timestamp
          type: timestamptz
          required: true
        # ... other columns

    # --- Define the logical primary key here ---
    identifier_fields:
      - event_uuid # Single column identifier
      # OR for a composite key:
      # - session_id
      # - event_timestamp

    partition_spec:
      # ...
    sort_order:
      # ...
    ```

3.  **Integrating into the Python Project:**
    *   **`definitions/validator.py`:** Add validation logic to ensure:
        *   If `identifier_fields` is present, the `properties['format-version']` is set to `2`.
        *   All column names listed in `identifier_fields` actually exist in the `schema.columns` list.
    *   **`iceberg/schema_builder.py`:**
        *   When parsing the validated definition, check if `identifier_fields` exists.
        *   If it does, iterate through the column names provided.
        *   For each name, find the corresponding `field_id` that was assigned during the schema building process for that column.
        *   Collect these `field_id`s into a list.
        *   When creating the `pyiceberg.schema.Schema` object, pass this list to the `identifier_field_ids` parameter:
            ```python
            # Inside schema_builder logic
            parsed_definition = ... # From definitions.parser
            pyiceberg_fields = []
            field_id_map = {} # Map column name -> assigned field_id
            next_id = 1
            for col_def in parsed_definition.schema.columns:
                field_id = next_id
                next_id += 1
                # ... build NestedField ...
                pyiceberg_fields.append(built_field)
                field_id_map[col_def.name] = field_id
                # ... handle nested types recursively ...

            identifier_ids = []
            if parsed_definition.identifier_fields:
                for id_col_name in parsed_definition.identifier_fields:
                    if id_col_name not in field_id_map:
                         raise SchemaBuildError(f"Identifier field '{id_col_name}' not found in schema columns.")
                    identifier_ids.append(field_id_map[id_col_name])

            # Pass the IDs when creating the schema
            final_schema = Schema(
                *pyiceberg_fields,
                schema_id=0, # Initial schema ID
                identifier_field_ids=identifier_ids # <-- HERE
            )
            return final_schema
            ```
    *   **`iceberg/table_creator.py`:** Ensure the `properties` dictionary passed to `catalog.create_table` includes `'format-version': 2` if identifier fields are defined.
    *   **`library/operations.py` (or `ManagedTable`):** The `upsert` method will now function correctly, as PyIceberg will use the `identifier_field_ids` from the loaded table's schema to perform the merge logic.

**Summary:**

Yes, you can define a logical primary key using `identifier_fields` in the YAML. This translates directly to Iceberg's mechanism for supporting row-level updates and deletes (like upserts) in V2 tables. The key steps are:

1.  Add `identifier_fields: [col1, col2, ...]` to your YAML.
2.  Ensure the table is explicitly set to `format-version: 2` in the YAML properties.
3.  Update the `schema_builder` in your Python project to look up the field IDs for these columns and pass them to the `Schema` constructor.
4.  Use operations like `ManagedTable.upsert()` which leverage these identifier fields.

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

You mention that: "Important Distinction: Unlike an RDBMS primary key, identifier_fields do not prevent you from writing duplicate rows using a standard append operation. Their purpose is to allow operations like upsert to find existing rows based on these fields and decide whether to update them or insert a new row. Equality deletes also use these fields to find rows to remove."

What about when im making SELECt queries? Like if session_id and event_timestamp make up a key and i query for a particular session_id, event_timestamp pair, its going to give me multiple rows? I don't want that

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

You are absolutely right to raise this concern. My previous explanation focused on the *write-time* behavior and the *purpose* of `identifier_fields` for upserts/deletes, but didn't fully address the read-time implications if duplicates exist.

Here's a breakdown of the situation and how to handle it:

1.  **Your Observation is Correct:** If you have only used `append` operations, and you happen to append rows that have the *same values* in the columns designated as `identifier_fields` (e.g., the same `session_id` and `event_timestamp`), then **yes, a `SELECT` query filtering *only* on those fields *will* return multiple rows.** Iceberg, by default for `append`, does not check for existing keys before writing.

2.  **Why Doesn't `append` Enforce Uniqueness?** This is a core design choice in Iceberg (and many data lake table formats) favoring **write performance and scalability**. Enforcing uniqueness on every append would require reading or indexing potentially vast amounts of data to check for existing keys before writing, which would drastically slow down ingestion, especially for streaming or large batch workloads.

3.  **How `identifier_fields` Help (During Writes):** The `identifier_fields` come into play when you use operations specifically designed for row-level changes:
    *   **`upsert` (or `MERGE` in engines like Spark):** When you `upsert` data, Iceberg *uses* the `identifier_fields` to determine if an incoming row matches an *existing* row. If it matches, the existing row is effectively updated (marked as deleted and a new version added); if it doesn't match, the new row is inserted. This *maintains* logical uniqueness *going forward* if you consistently use `upsert`.
    *   **Equality Deletes:** These operations also use `identifier_fields` to find and delete *all* matching rows based on the key.

4.  **Strategies to Ensure Uniqueness for `SELECT` Queries:**

    *   **Strategy 1: Use `upsert` Consistently (Recommended):**
        *   **How:** After an initial bulk load (which could be `overwrite` or `append`), perform all subsequent writes using the `ManagedTable.upsert()` method provided by your library.
        *   **Result:** Each `upsert` operation ensures that for any given combination of values in the `identifier_fields`, only one "active" row exists in the current table snapshot. SELECT queries against the current snapshot will then return only one row per unique key combination.
        *   **Caveat:** The underlying data files might still contain older versions of the rows until compaction runs, but queries reading the table's current metadata/snapshot won't see those duplicates.

    *   **Strategy 2: Periodic Deduplication/Merging:**
        *   **How:** Allow appends (which might create duplicates). Then, periodically run a separate process (e.g., using Spark's `MERGE INTO` statement or a custom job) that reads the table, deduplicates based on the `identifier_fields` (keeping the latest based on `event_timestamp` perhaps), and writes the unique results back, overwriting the duplicates.
        *   **Result:** SELECT queries will return unique rows *after* the deduplication job runs. There might be temporary duplicates between runs.
        *   **Tooling:** This often requires a more powerful engine like Spark, Flink, or potentially advanced features in DuckDB/Daft/Polars connected via PyIceberg. Your simple library might not perform this directly.

    *   **Strategy 3: Query-Time Deduplication:**
        *   **How:** Accept that duplicates might exist in the table. When querying (in Athena, Spark, DuckDB, etc.), use window functions to select only one row per key.
            ```sql
            -- Example in SQL (Athena/Spark/DuckDB)
            SELECT *
            FROM (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY session_id, event_timestamp ORDER BY some_other_determining_column DESC) as rn
                FROM your_iceberg_table
                WHERE session_id = 'some_value' AND event_timestamp = 'some_timestamp' -- Optional initial filter
            )
            WHERE rn = 1;
            ```
        *   **Result:** You get unique rows in your query result, but the underlying table still contains duplicates. This puts the burden on every query author.

**Recommendation for Your Project:**

Given the goal of providing a user-friendly Python library:

*   **Emphasize the `upsert` method:** Clearly document that if users require uniqueness based on the `identifier_fields`, they **should use the `ManagedTable.upsert()` method** for writes after the initial load. This is the most idiomatic Iceberg way to handle this within the table format itself.
*   **Explain the `append` behavior:** Be explicit in the documentation that `ManagedTable.append()` does *not* check for duplicates based on `identifier_fields`.
*   **Initial Load:** For the very first population of the table, `append` or `overwrite` is fine. It's the subsequent modifications where `upsert` becomes crucial for maintaining uniqueness.

In summary: Don't think of `identifier_fields` as a constraint like an RDBMS primary key, but as a *definition* used by specific operations (`upsert`, equality deletes) to identify rows. To guarantee uniqueness visible to `SELECT`, you must use write operations that leverage this definition, primarily `upsert`.

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

Does this mean reads aren't performant?

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

No, the fact that `append` doesn't enforce uniqueness **does not inherently mean that reads are not performant** in Iceberg. Iceberg is specifically designed for highly performant reads on large datasets, primarily through **metadata pruning**.

Here's why reads remain performant and how the duplicate issue relates:

1.  **Metadata Pruning (The Key to Performance):**
    *   Iceberg stores detailed statistics (min/max values for columns) within its metadata for each data file (e.g., Parquet file).
    *   It also knows exactly which partition data resides in (based on metadata, not slow directory listings).
    *   When you run a `SELECT` query with a `WHERE` clause (e.g., `WHERE session_id = 'abc'` or `WHERE event_timestamp BETWEEN x AND y`), the query engine first consults the Iceberg metadata.
    *   It uses the partition information and the min/max statistics to determine which data files *absolutely cannot* contain matching data.
    *   **Crucially, it completely skips reading those irrelevant files.** This is often the biggest factor in read performance, as it drastically reduces the amount of I/O required.

2.  **Impact of Duplicates on Pruning:**
    *   The existence of duplicate rows based on your logical `identifier_fields` **does not break this pruning mechanism.**
    *   If multiple files contain rows with `session_id = 'xyz'` and `event_timestamp = '123'`, Iceberg's metadata will indicate that those files *might* contain relevant data based on their overall min/max values for those columns. The query engine will still read *only* those potentially relevant files.
    *   The pruning happens at the *file* level based on the *range* of values within the file, not based on individual key uniqueness across the whole table during the pruning phase.

3.  **Where Duplicates *Can* Affect Performance (Indirectly or at Query Time):**
    *   **Increased Data Read (Slightly):** If duplicates exist, the files containing them *will* be read (assuming they pass pruning). You might read slightly more data than if duplicates were strictly prevented *if* the duplicates are spread across multiple files that would otherwise be pruned. However, the primary benefit of skipping large numbers of totally irrelevant files usually outweighs this.
    *   **Query-Time Deduplication Overhead:** If you choose **Strategy 3** (handling duplicates in the `SELECT` query using `ROW_NUMBER()`), then *yes*, the query engine has to do extra work *after* reading the data to perform the deduplication. This adds processing time to the query itself, but it doesn't negate the initial I/O savings from Iceberg's file skipping.
    *   **Small Files (from `upsert`/`delete`):** Using `upsert` frequently *can* lead to smaller data files and the creation of delete files. Reading many small files can be less efficient than reading fewer large ones. This is why **compaction** (rewriting small files into larger ones and applying deletes) is an important maintenance operation for Iceberg tables with frequent updates or deletes to maintain peak read performance.

**In Summary:**

Iceberg's read performance primarily comes from **avoiding reading unnecessary data files** thanks to its rich metadata. The potential presence of duplicates (if you only use `append`) doesn't fundamentally break this mechanism.

*   Reads remain highly performant due to **metadata-driven file skipping**.
*   If you need unique results, using `upsert` for writes is the recommended way to manage this within Iceberg, maintaining good read performance for queries against the current snapshot.
*   If you allow duplicates via `append` and handle them at query time, the performance impact comes from the *query processing step* (e.g., the window function), not typically from the initial Iceberg data loading/scanning phase being inherently slow.
*   Regular table maintenance (compaction) is important, especially for tables with many updates/deletes, to optimize read performance further by managing file sizes and applying deletes.

───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────
───────────────────────────────────────────────────────────────

