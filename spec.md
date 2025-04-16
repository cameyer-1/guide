I want to set up an API on AWS, it'll just be single POST endpoint where the request follows this RequestModel:
```
from pydantic import BaseModel
from datetime import date
from enum import Enum


class Department(str, Enum):
    AE = "AE"
    CMF = "CMF"
    ABC = "ABC"
    GG = "GG"
	ADMIN = "ADMIN"

# Reference model
class Reference(BaseModel):
    id: str
    type: str

# Package model
class Package(BaseModel):
    name: str
    references: list[Reference]

# Request model
class RequestModel(BaseModel):
    packages: list[Package]
    business_unit: Department
    requested_by: Department
    last_updated_by: Department
    request_date: date
    last_updated_date: date
	
class DatabaseRow(BaseModel):
	reference_id: str
	reference_type: str
	package: str
	business_unit: Department
	requested_by: Department
    last_updated_by: Department
    request_date: date
    last_updated_date: date
```

The POST request will take the RequestModel object, and turn it into a DB row to be stored in AWS, so that its queryable with AWS Athena. My team uses Chalice for exposing endpoints. I want to store this stuff as parquet for Athena to read. The database will be df_trusted_prod and the table will be security_of_interest_pit where pit stands for Point in Time, and the bucket will use the same naming scheme.

The business_unit which will be part of the endpoint, e.g. POST /v1/security-of-interest/business-unit/{business_unit}/
The request_date and last_updated_date will be the same value, and they will be inferred from the date the request was made.

I am interested in seeing how AWS IAM is set up so that only users of that department can make a call for their business_unit. Assume that for each entry: business_unit, requested_by, and last_updated_by will always be the same value for now.
Assume business_unit, requested_by, and last_updated_by won't be in the request, as they will be inferred from the endpoint URL.

Next, lets say i want to maintain another table alongside this one, called `security_of_interest_latest`. While they will be structurally the same, the difference between `security_of_interest_latest` and `security_of_interest_pit` is that `security_of_interest_latest` will only contain the latest request for any (business_unit, package) pair. For example, the caller first makes the request:
```
POST /dev/v1/security-of-interest/business-unit/AE/ HTTP/1.1

{
  "packages": [
    {
      "name": "Equity_Swaps_Package_1",
      "references": [
        {"id": "REF123", "type": "ISIN"},
        {"id": "REF456", "type": "CUSIP"}
      ]
    },
    {
      "name": "Options_Package_A",
      "references": [
        {"id": "REF789", "type": "SEDOL"}
      ]
    }
  ]
}
```
This would create three rows, one for each reference.
But 10 minutes later, he changes his mind and wants to remove a reference from "Equity_Swaps_Package_1" by sending this request:
```
POST /dev/v1/security-of-interest/business-unit/AE/ HTTP/1.1

{
  "packages": [
    {
      "name": "Equity_Swaps_Package_1",
      "references": [
        {"id": "REF123", "type": "ISIN"}
      ]
    }
  ]
}
```
This will overwrite everything for that business_unit, it will go from three reference rows down to just one.

Presumably, this chalice configuration and backend will be hosted on lambda. Show me the backend code for this, along with the Athena schema.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

Okay, let's set up this Chalice API, S3 storage with Parquet, Athena tables, and the IAM structure.

We'll use the `awswrangler` library, which significantly simplifies writing partitioned Parquet files to S3 and managing Glue Data Catalog tables (which Athena uses).

**1. Project Setup & Dependencies**

Make sure you have Chalice and the necessary libraries installed:

```bash
pip install chalice boto3 pandas pyarrow awswrangler pydantic
```

Create a Chalice project (if you haven't already):

```bash
chalice new-project security-of-interest-api
cd security-of-interest-api
```

Your `requirements.txt` should include:

```
chalice
boto3
pandas
pyarrow
awswrangler
pydantic
```

**2. Chalice Application Code (`app.py`)**

```python
import os
import logging
from datetime import date
from enum import Enum
from typing import List

import awswrangler as wr
import pandas as pd
from chalice import Chalice, Response, IAMAuthorizer, BadRequestError, ChaliceViewError
from pydantic import BaseModel, Field, ValidationError

# --- Configuration ---
# Best practice: Load from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET", "df-trusted-prod-data") # Example bucket name
GLUE_DATABASE = os.environ.get("GLUE_DATABASE", "df_trusted_prod")
PIT_TABLE_NAME = "security_of_interest_pit"
LATEST_TABLE_NAME = "security_of_interest_latest"
S3_PIT_PREFIX = f"s3://{S3_BUCKET}/{PIT_TABLE_NAME}/"
S3_LATEST_PREFIX = f"s3://{S3_BUCKET}/{LATEST_TABLE_NAME}/"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Models ---

class Department(str, Enum):
    AE = "AE"
    CMF = "CMF"
    ABC = "ABC"
    GG = "GG"
    ADMIN = "ADMIN" # Added ADMIN based on your model definition

# Reference model (part of the incoming request)
class Reference(BaseModel):
    id: str
    type: str

# Package model (part of the incoming request)
class Package(BaseModel):
    name: str
    references: list[Reference]

# Actual Request model for the API (doesn't include inferred fields)
class ApiRequestModel(BaseModel):
    packages: list[Package]

# Target Database Row structure (used for DataFrame and Parquet schema)
class DatabaseRow(BaseModel):
    reference_id: str
    reference_type: str
    package: str
    business_unit: Department
    requested_by: Department
    last_updated_by: Department
    request_date: date
    last_updated_date: date

# --- Chalice App ---

app = Chalice(app_name='security-of-interest-api')
# Use AWS IAM for authorization
authorizer = IAMAuthorizer()

@app.route('/v1/security-of-interest/business-unit/{business_unit}', methods=['POST'], authorizer=authorizer)
def update_security_of_interest(business_unit: str):
    """
    Receives security of interest data for a specific business unit,
    validates it, transforms it, and stores it in S3 for Athena.
    Updates both PIT (Point-in-Time) and LATEST tables.
    """
    # --- Input Validation ---
    try:
        # Validate business_unit from path against the Enum
        business_unit_enum = Department(business_unit.upper())
        logger.info(f"Processing request for business_unit: {business_unit_enum.value}")
    except ValueError:
        logger.error(f"Invalid business_unit provided in path: {business_unit}")
        raise BadRequestError(f"Invalid business_unit: '{business_unit}'. Must be one of {list(Department.__members__.keys())}")

    try:
        # Parse and validate the request body
        request_data = ApiRequestModel.parse_obj(app.current_request.json_body)
        logger.info(f"Received {len(request_data.packages)} packages in the request.")
    except ValidationError as e:
        logger.error(f"Request body validation failed: {e}")
        raise BadRequestError(f"Invalid request body: {e}")
    except Exception as e:
        logger.error(f"Could not parse request body: {e}")
        raise BadRequestError("Could not parse request body. Ensure it's valid JSON.")

    # --- Data Transformation ---
    current_date = date.today()
    db_rows = []

    if not request_data.packages:
         logger.warning(f"Received empty packages list for business unit {business_unit_enum.value}. This will effectively clear the 'latest' data.")
         # Even if packages list is empty, we might want to record this 'clearing' action in PIT
         # and ensure the latest partition is overwritten with empty data. Proceeding.

    for package in request_data.packages:
        if not package.references:
            logger.warning(f"Package '{package.name}' has an empty references list. Skipping references for this package.")
            # Decide if a package with no references should still exist in 'latest' or be removed.
            # Current logic: If a package is listed with no references, it means *remove* all previous references for this package.
            # If the intent is different, adjust logic here.

        for reference in package.references:
            row_data = {
                "reference_id": reference.id,
                "reference_type": reference.type,
                "package": package.name,
                "business_unit": business_unit_enum,
                "requested_by": business_unit_enum, # As per requirement
                "last_updated_by": business_unit_enum, # As per requirement
                "request_date": current_date,
                "last_updated_date": current_date # As per requirement
            }
            db_rows.append(DatabaseRow(**row_data).dict()) # Convert Pydantic model to dict

    # Create Pandas DataFrame
    if db_rows:
        df = pd.DataFrame(db_rows)
        # Ensure correct data types, especially for dates
        df['request_date'] = pd.to_datetime(df['request_date']).dt.date
        df['last_updated_date'] = pd.to_datetime(df['last_updated_date']).dt.date
        # Ensure enum columns are strings for Parquet/Athena compatibility
        for col in ['business_unit', 'requested_by', 'last_updated_by']:
             df[col] = df[col].astype(str)
        logger.info(f"Created DataFrame with {len(df)} rows.")
    else:
        # Handle the case where the input results in zero rows (e.g., empty packages list)
        # Create an empty DataFrame with the correct schema to ensure overwrites work correctly
        df = pd.DataFrame(columns=DatabaseRow.__fields__.keys())
        # Cast columns even if empty to ensure schema consistency if needed by wrangler
        df = df.astype({
            "reference_id": str, "reference_type": str, "package": str,
            "business_unit": str, "requested_by": str, "last_updated_by": str,
            "request_date": object, # Pandas uses object for Date columns
            "last_updated_date": object
        })
        logger.info("Created empty DataFrame as no valid references were provided.")


    # --- Data Storage (S3 & Glue Data Catalog) ---
    try:
        # 1. Write to PIT table (Append mode, partitioned by business_unit and date)
        logger.info(f"Writing {len(df)} rows to PIT table: {GLUE_DATABASE}.{PIT_TABLE_NAME}")
        wr.s3.to_parquet(
            df=df,
            path=S3_PIT_PREFIX,
            dataset=True,
            database=GLUE_DATABASE,
            table=PIT_TABLE_NAME,
            mode="append",
            partition_cols=["business_unit", "request_date"],
            dtype={ # Explicitly map date type for Glue/Athena
                'request_date': 'date',
                'last_updated_date': 'date'
            },
            catalog_versioning=True, # Optional: enable Glue versioning
            schema_evolution=True # Allow schema evolution if needed later
        )
        logger.info("Successfully wrote to PIT table.")

        # 2. Write to LATEST table (Overwrite specific business_unit partition)
        #    Use ONLY business_unit as partition key here.
        logger.info(f"Writing {len(df)} rows to LATEST table: {GLUE_DATABASE}.{LATEST_TABLE_NAME} (overwriting partition for {business_unit_enum.value})")
        wr.s3.to_parquet(
            df=df,
            path=S3_LATEST_PREFIX,
            dataset=True,
            database=GLUE_DATABASE,
            table=LATEST_TABLE_NAME,
            mode="overwrite_partitions", # Key difference: Overwrites partitions matching data
            partition_cols=["business_unit"],
            dtype={ # Explicitly map date type for Glue/Athena
                'request_date': 'date',
                'last_updated_date': 'date'
            },
            catalog_versioning=True,
            schema_evolution=True
        )
        logger.info("Successfully wrote to LATEST table.")

    except Exception as e:
        logger.exception(f"Failed to write data to S3/Glue: {e}")
        # Consider more specific error handling if needed
        raise ChaliceViewError(f"Internal server error writing data: {e}")

    return Response(
        body={'message': f'Successfully processed {len(df)} records for business unit {business_unit_enum.value}.'},
        status_code=201 # Use 201 Created for successful POST actions
    )

# Example of how to get caller identity if needed inside the function (though not used for logic here)
# def get_caller_info():
#     context = app.current_request.context
#     identity = context.get('identity', {})
#     caller_arn = identity.get('caller')
#     user_arn = identity.get('userArn')
#     # You might parse group names or tags from the ARN or use Cognito identity info
#     logger.info(f"Caller ARN: {caller_arn}, User ARN: {user_arn}")
```

**3. IAM Setup**

This is crucial for restricting access based on department.

*   **Lambda Execution Role:** When you deploy your Chalice app (`chalice deploy`), it creates an IAM role for the Lambda function. This role needs permissions to:
    *   Write logs to CloudWatch (`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`).
    *   Write to the S3 Bucket (`s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` - needed for `overwrite_partitions`, `s3:ListBucket` might be needed depending on wrangler usage). Target the specific bucket: `arn:aws:s3:::df-trusted-prod-data/*` and `arn:aws:s3:::df-trusted-prod-data`.
    *   Interact with AWS Glue Data Catalog (`glue:GetDatabase`, `glue:CreateTable`, `glue:GetTable`, `glue:UpdateTable`, `glue:CreatePartition`, `glue:BatchCreatePartition`, `glue:GetPartitions`, `glue:BatchGetPartition`). Target the specific database: `arn:aws:glue:REGION:ACCOUNT_ID:database/df_trusted_prod`, `arn:aws:glue:REGION:ACCOUNT_ID:table/df_trusted_prod/*`, `arn:aws:glue:REGION:ACCOUNT_ID:catalog`. `awswrangler` handles table creation/updates, so these are important.

    You can manage this role via the AWS Console or by configuring it in Chalice's `config.json`.

*   **API Gateway IAM Authorization:** You've specified `authorizer=iam()` in Chalice. This tells API Gateway to use AWS IAM credentials to authorize requests.

*   **IAM Users/Groups and Policies for Callers:**
    1.  **Create IAM Groups:** Create groups corresponding to your departments (e.g., `Department-AE`, `Department-CMF`, `Department-ABC`, `Department-GG`, `Department-ADMIN`).
    2.  **Assign Users:** Assign the IAM users who will call the API to their respective department group.
    3.  **Create IAM Policies per Department:** This is where the restriction happens. You need a policy for *each* group that allows invoking *only* their specific endpoint path.

        *Policy Example for `Department-AE` Group:*
        ```json
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "execute-api:Invoke",
                    "Resource": "arn:aws:execute-api:YOUR_REGION:YOUR_ACCOUNT_ID:YOUR_API_ID/YOUR_STAGE/POST/v1/security-of-interest/business-unit/AE"
                }
            ]
        }
        ```
        *   **Replace:** `YOUR_REGION`, `YOUR_ACCOUNT_ID`, `YOUR_API_ID`, `YOUR_STAGE` (e.g., `dev`, `prod`). You find the `API_ID` after deploying the Chalice app.
        *   **Resource ARN:** The key is the `Resource` ARN, which specifically targets the `POST` method on the `/v1/security-of-interest/business-unit/AE` path.
        *   **Create Similar Policies:** Create analogous policies for `CMF`, `ABC`, `GG`, `ADMIN`, changing the final part of the resource ARN (`/AE`, `/CMF`, etc.).
    4.  **Attach Policies:** Attach the corresponding policy to each department group (e.g., attach the `AE-InvokePolicy` to the `Department-AE` group).

Now, an IAM user in the `Department-CMF` group can *only* successfully call `POST /v1/security-of-interest/business-unit/CMF` (assuming they sign their request correctly with their AWS credentials). Trying to call the `/AE` endpoint will result in a 403 Forbidden error from API Gateway.

**4. Athena Table Schema (DDL)**

`awswrangler` will attempt to create/update these tables in the Glue Data Catalog for you if they don't exist or if the schema changes (because we set `dataset=True`). However, it's good practice to know the DDL. You can also create them manually in Athena first.

*   **`security_of_interest_pit` Table:**

```sql
CREATE EXTERNAL TABLE `df_trusted_prod`.`security_of_interest_pit`(
  `reference_id` string,
  `reference_type` string,
  `package` string,
  `requested_by` string,
  `last_updated_by` string,
  `last_updated_date` date)
PARTITIONED BY (
  `business_unit` string,
  `request_date` date)
ROW FORMAT SERDE
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
STORED AS INPUTFORMAT
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
OUTPUTFORMAT
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION
  's3://df-trusted-prod-data/security_of_interest_pit/'
TBLPROPERTIES (
  'classification'='parquet',
  'parquet.compression'='SNAPPY'); -- Or GZIP, etc. awswrangler defaults usually good.
```
*After creating, run `MSCK REPAIR TABLE df_trusted_prod.security_of_interest_pit;` in Athena to discover partitions if you created the table manually before data existed.*

*   **`security_of_interest_latest` Table:**

```sql
CREATE EXTERNAL TABLE `df_trusted_prod`.`security_of_interest_latest`(
  `reference_id` string,
  `reference_type` string,
  `package` string,
  `requested_by` string,
  `last_updated_by` string,
  `request_date` date,          -- Note: request_date is data, not partition
  `last_updated_date` date)    -- Note: last_updated_date is data, not partition
PARTITIONED BY (
  `business_unit` string)        -- Only partitioned by business_unit
ROW FORMAT SERDE
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
STORED AS INPUTFORMAT
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
OUTPUTFORMAT
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION
  's3://df-trusted-prod-data/security_of_interest_latest/'
TBLPROPERTIES (
  'classification'='parquet',
  'parquet.compression'='SNAPPY');
```
*After creating, run `MSCK REPAIR TABLE df_trusted_prod.security_of_interest_latest;` in Athena to discover partitions if you created the table manually before data existed.*

**Explanation Summary:**

1.  **Chalice API (`app.py`):** Defines the endpoint, uses IAM authorization, validates path parameter (`business_unit`) and request body (`ApiRequestModel`), transforms data into `DatabaseRow` format, gets the current date.
2.  **Pydantic Models:** Ensure data consistency and validation. `ApiRequestModel` is what the endpoint expects; `DatabaseRow` is the target schema.
3.  **AWS Wrangler (`wr.s3.to_parquet`):** Handles writing Pandas DataFrames to S3 as partitioned Parquet files. Critically, it also interacts with the Glue Data Catalog to create/update table schemas and partitions.
    *   `_pit`: `mode="append"`, partitioned by `business_unit` and `request_date`. New data is added alongside old data.
    *   `_latest`: `mode="overwrite_partitions"`, partitioned only by `business_unit`. When new data arrives for `AE`, `awswrangler` deletes the existing objects in the `s3://.../business_unit=AE/` prefix and writes the new data, effectively replacing the *entire* dataset for that `business_unit`.
4.  **IAM:** API Gateway uses IAM roles/users/groups and policies to control *who* can call *which* specific endpoint path (`execute-api:Invoke` action on the specific resource ARN). The Lambda function needs its *own* role to interact with S3 and Glue.
5.  **Athena:** Uses the Glue Data Catalog tables defined over the S3 Parquet data. Partitioning is key for performance and for the `overwrite_partitions` logic in the `_latest` table.

This setup provides a robust, scalable, and secure way to ingest your data, maintain a full history (`_pit`), keep track of the current state (`_latest`), and query it efficiently using Athena, while enforcing departmental access controls at the API layer.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

Okay, here is a sequence diagram illustrating the flow for the POST request, incorporating the IAM authorization check, Lambda processing, and interactions with S3 and Glue for both the PIT and LATEST tables.

We'll use Mermaid syntax, which is commonly used for text-based diagrams.

```mermaid
sequenceDiagram
    participant C as Client (IAM User/Role)
    participant APIGW as API Gateway
    participant IAM as AWS IAM Service
    participant L as Lambda (Chalice App)
    participant S3 as S3 Bucket (df-trusted-prod-data)
    participant Glue as Glue Data Catalog

    C->>+APIGW: POST /v1/security-of-interest/business-unit/{business_unit} \n (Request Body, Signed w/ AWS Credentials)

    APIGW->>+IAM: Validate Caller Credentials & Permissions
    Note over APIGW, IAM: Check if caller's policy allows 'execute-api:Invoke' on the specific resource ARN (e.g., .../POST/v1/.../business-unit/AE)
    IAM-->>-APIGW: Authorization Decision (Allow/Deny)

    alt Authorized
        APIGW->>+L: Invoke Function (Passes path params, body, context)
        L->>L: Parse business_unit from path
        L->>L: Validate business_unit against Enum
        L->>L: Parse and validate request body (Pydantic ApiRequestModel)
        L->>L: Get current date
        L->>L: Transform request into DataFrame (DatabaseRow format) \n (Adds business_unit, dates, etc.)

        Note over L: Using awswrangler for S3/Glue operations

        %% --- PIT Table Interaction ---
        L->>+S3: wr.s3.to_parquet (PIT) \n Path: s3://.../security_of_interest_pit/ \n Mode: append \n Partitions: business_unit, request_date \n Data: DataFrame
        S3-->>-L: Parquet file(s) written to S3
        L->>+Glue: wr.s3.to_parquet (PIT) \n Updates Glue Table: security_of_interest_pit \n Action: Add/update partitions (e.g., business_unit=AE/request_date=YYYY-MM-DD)
        Glue-->>-L: Catalog Updated (PIT)

        %% --- LATEST Table Interaction ---
        Note right of L: 'overwrite_partitions' mode first deletes existing objects in the target partition(s).
        L->>+S3: wr.s3.to_parquet (LATEST) - Step 1: Delete \n Path: s3://.../security_of_interest_latest/business_unit={business_unit}/ \n Action: Delete existing objects in this prefix
        S3-->>-L: Existing partition objects deleted
        L->>+S3: wr.s3.to_parquet (LATEST) - Step 2: Write \n Path: s3://.../security_of_interest_latest/ \n Mode: overwrite_partitions \n Partitions: business_unit \n Data: DataFrame (same data as PIT write)
        S3-->>-L: New Parquet file(s) written to S3 partition
        L->>+Glue: wr.s3.to_parquet (LATEST) \n Updates Glue Table: security_of_interest_latest \n Action: Ensure partition exists (business_unit={business_unit}), update table metadata if needed
        Glue-->>-L: Catalog Updated (LATEST)

        L->>L: Prepare Success Response (HTTP 201)
        L-->>-APIGW: Return Success Response

        APIGW-->>-C: HTTP 201 Created Response

    else Denied (Not Authorized)
        APIGW-->>-C: HTTP 403 Forbidden Response
    end
```

**Explanation of the Diagram:**

1.  **Client Request:** The IAM User (or an application using an IAM Role) sends a POST request, signed with their AWS credentials, to the specific API Gateway endpoint.
2.  **IAM Authorization:** API Gateway intercepts the request and validates the signature and associated IAM policy against the AWS IAM service. It checks if the policy attached to the caller's user/role grants `execute-api:Invoke` permission on the *exact* resource ARN requested (e.g., `/v1/security-of-interest/business-unit/AE`).
3.  **Conditional Flow (Auth):**
    *   If **Denied**, API Gateway immediately returns a 403 Forbidden error.
    *   If **Authorized**, API Gateway proceeds to invoke the backend Lambda function.
4.  **Lambda Invocation:** API Gateway passes the request details (headers, path parameters like `{business_unit}`, the request body, and context like caller identity) to the Chalice Lambda function.
5.  **Lambda Processing:**
    *   The function validates the path parameter and request body using Pydantic.
    *   It transforms the incoming data into the target `DatabaseRow` structure, creating a Pandas DataFrame. This includes adding the `business_unit` from the path and the current `request_date`/`last_updated_date`.
6.  **PIT Table Write (Append):**
    *   The Lambda uses `awswrangler` to write the DataFrame to the `security_of_interest_pit` location in S3.
    *   `mode="append"` ensures existing data isn't touched.
    *   `partition_cols=["business_unit", "request_date"]` tells `awswrangler` to structure the S3 path and update Glue accordingly (e.g., `s3://.../business_unit=AE/request_date=2023-10-27/file.parquet`).
    *   `awswrangler` interacts with Glue to register these new partitions in the `security_of_interest_pit` table.
7.  **LATEST Table Write (Overwrite Partitions):**
    *   The Lambda uses `awswrangler` again, but this time targeting the `security_of_interest_latest` location and table.
    *   `mode="overwrite_partitions"` tells `awswrangler` to replace data *only* for the partition(s) present in the *current* DataFrame being written. Since the DataFrame contains data only for the single `business_unit` from the URL, `awswrangler` first *deletes* all existing S3 objects under the corresponding S3 prefix (e.g., `s3://.../security_of_interest_latest/business_unit=AE/`).
    *   Then, it writes the *new* Parquet file(s) for that `business_unit` partition.
    *   `partition_cols=["business_unit"]` is used here.
    *   `awswrangler` interacts with Glue to ensure the `business_unit` partition exists and points to the new data in the `security_of_interest_latest` table.
8.  **Response:** The Lambda prepares a success (HTTP 201 Created) response.
9.  **Return Flow:** The Lambda returns the response to API Gateway, which relays it back to the original Client.

This diagram shows the clear separation of concerns and the specific interactions needed to maintain both the historical (PIT) and current-state (LATEST) views of the data, triggered by a single, authorized API call.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

Okay, let's break down the execution flow step-by-step, starting from the moment the user sends the request:

**Phase 1: Request Initiation & API Gateway Handling**

1.  **Client Sends Request:** An authorized client (e.g., a script, application, or user via a tool like Postman/curl) crafts an HTTP POST request.
    *   **Target URL:** `/v1/security-of-interest/business-unit/{business_unit}` (e.g., `/v1/security-of-interest/business-unit/AE`)
    *   **Method:** `POST`
    *   **Headers:** Must include AWS Signature Version 4 headers, generated using the client's IAM user/role credentials. This proves the client's identity to AWS.
    *   **Body:** A JSON payload matching the structure of `ApiRequestModel` (containing the `packages` list).

2.  **API Gateway Receives Request:** The request hits the AWS API Gateway endpoint configured by Chalice.

3.  **IAM Authorization Check (Critical Step):**
    *   Because the Chalice route is decorated with `@app.route(..., authorizer=authorizer)` where `authorizer` is `IAMAuthorizer()`, API Gateway performs an IAM authorization check *before* invoking the Lambda.
    *   It extracts the caller's identity from the AWS Signature headers.
    *   It checks the IAM policies attached to that caller (their IAM user or the assumed role).
    *   **Verification:** It specifically checks if the policy grants the `execute-api:Invoke` action on the *exact* resource ARN corresponding to this specific request (e.g., `arn:aws:execute-api:REGION:ACCOUNT_ID:API_ID/STAGE/POST/v1/security-of-interest/business-unit/AE`).
    *   **Decision:**
        *   **If Denied:** The caller's policy does *not* allow access to this specific path/method. API Gateway immediately stops processing and sends an `HTTP 403 Forbidden` response back to the client. The Lambda function is *never* invoked.
        *   **If Allowed:** The policy grants permission. API Gateway proceeds to the next step.

**Phase 2: Lambda Function Execution (Chalice App)**

4.  **API Gateway Invokes Lambda:** API Gateway triggers the backend Lambda function (`update_security_of_interest`) associated with the matched route. It passes:
    *   The path parameter (`business_unit` = "AE" in our example).
    *   The request body (the JSON payload).
    *   Context information (including caller identity, though not used directly in the logic here).

5.  **Function Execution Begins:** The Python code in `app.py` starts running within the Lambda environment.

6.  **Path Parameter Validation:**
    *   The code receives `business_unit` (e.g., "AE") as a string function argument.
    *   `business_unit_enum = Department(business_unit.upper())` attempts to convert this string into a member of the `Department` Enum.
    *   If the string is not a valid member (e.g., "XYZ"), a `ValueError` occurs, the `except` block catches it, logs an error, and raises a `BadRequestError`. Chalice translates this into an `HTTP 400 Bad Request` response sent back through API Gateway.

7.  **Request Body Parsing & Validation:**
    *   `app.current_request.json_body` accesses the JSON payload sent by the client.
    *   `ApiRequestModel.parse_obj(...)` uses Pydantic to:
        *   Parse the JSON into a Python object.
        *   Validate that the object's structure and data types conform *exactly* to the `ApiRequestModel` definition (e.g., checks if `packages` is a list, if items have `name` and `references`, etc.).
    *   If validation fails (e.g., missing required field, wrong data type), a `ValidationError` occurs, the `except` block catches it, logs the specific validation errors, and raises a `BadRequestError` (leading to an `HTTP 400 Bad Request` response).

8.  **Data Transformation & Enrichment:**
    *   `current_date = date.today()` captures the date the Lambda function is running.
    *   An empty list `db_rows` is created to hold the flattened data.
    *   The code iterates through each `package` in the validated `request_data.packages`.
    *   For each `package`, it iterates through each `reference` in `package.references`.
    *   Inside the inner loop (for each reference), it builds a dictionary representing a single row for the database:
        *   Copies `id` and `type` from the reference.
        *   Copies `name` from the package.
        *   Adds `business_unit`, `requested_by`, `last_updated_by` using the validated `business_unit_enum` from the path parameter.
        *   Adds `request_date` and `last_updated_date` using the `current_date`.
    *   `DatabaseRow(**row_data).dict()` validates this constructed dictionary against the `DatabaseRow` model and converts it back to a dictionary. This ensures the data going into the DataFrame matches the target schema.
    *   This row dictionary is appended to the `db_rows` list.

9.  **DataFrame Creation:**
    *   `df = pd.DataFrame(db_rows)` creates a Pandas DataFrame from the list of dictionaries. Each dictionary becomes a row in the DataFrame.
    *   Data types are explicitly set (dates to date objects, enums to strings) to ensure compatibility with Parquet and Athena.
    *   An empty DataFrame with the correct schema is created if `db_rows` is empty.

**Phase 3: Data Persistence (S3 & Glue via AWS Wrangler)**

10. **Write to PIT Table (Append):**
    *   `wr.s3.to_parquet(...)` is called for the Point-in-Time (PIT) table.
    *   **Action:** It writes the DataFrame `df` to S3.
    *   **Location:** `s3://df-trusted-prod-data/security_of_interest_pit/`
    *   **Partitioning:** Uses `partition_cols=["business_unit", "request_date"]`. The data is written into nested folders like `.../business_unit=AE/request_date=2023-10-27/`.
    *   **Mode:** `mode="append"`. This crucial setting tells `awswrangler` to *add* new Parquet files to the specified location/partition without deleting any existing files.
    *   **Glue Integration:** (`dataset=True`, `database=...`, `table=...`) `awswrangler` also interacts with the AWS Glue Data Catalog:
        *   It ensures the `df_trusted_prod` database and `security_of_interest_pit` table exist (creating/updating if necessary, based on DataFrame schema).
        *   It registers the *new partitions* (e.g., `business_unit=AE`, `request_date=2023-10-27`) in the Glue table, pointing them to the newly written S3 files.

11. **Write to LATEST Table (Overwrite Partition):**
    *   `wr.s3.to_parquet(...)` is called again, this time for the "Latest" table.
    *   **Action:** It writes the *same* DataFrame `df` to S3 again.
    *   **Location:** `s3://df-trusted-prod-data/security_of_interest_latest/`
    *   **Partitioning:** Uses `partition_cols=["business_unit"]`. Data is written into folders like `.../business_unit=AE/`.
    *   **Mode:** `mode="overwrite_partitions"`. This crucial setting tells `awswrangler`:
        1.  Identify the partition(s) present in the input DataFrame `df` (in this case, only `business_unit=AE`).
        2.  **Delete all existing S3 objects** under the corresponding S3 prefix (e.g., `s3://df-trusted-prod-data/security_of_interest_latest/business_unit=AE/`).
        3.  Write the *new* Parquet files from the DataFrame `df` into that now-empty S3 prefix.
    *   **Glue Integration:** `awswrangler` ensures the `df_trusted_prod` database and `security_of_interest_latest` table exist in Glue and that the partition (`business_unit=AE`) points to the newly written S3 data.

**Phase 4: Response Generation & Return**

12. **Prepare Success Response:** If both `to_parquet` calls complete without exceptions:
    *   A success message dictionary is created.
    *   `Response(body=..., status_code=201)` constructs the final HTTP response object. `201 Created` is appropriate for a successful POST that results in resource creation/update.

13. **Handle Potential Errors:** If any exception occurs during the S3/Glue writing process (e.g., S3 permissions issue, Glue API error):
    *   The `except Exception as e:` block catches the error.
    *   The error is logged using `logger.exception(...)`.
    *   A `ChaliceViewError` is raised. Chalice translates this into an `HTTP 500 Internal Server Error` response.

14. **Lambda Returns Response:** The Lambda function finishes and returns the prepared `Response` object (either the 201 success or a 500/400 error) back to API Gateway.

15. **API Gateway Returns Response:** API Gateway forwards the response (status code, headers, body) received from the Lambda function back to the original client that made the request.

This completes the lifecycle of a single request, covering authorization, validation, transformation, dual-table persistence with different strategies (append vs. overwrite), and response handling.
