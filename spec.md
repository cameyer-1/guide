The task is to produce tables that are accessible through AWS Athena, where the table data will be stored in AWS S3.
There are two tables: security_of_interest_pit (where PIT stands for point in time, more on this later) and security_of_interest_latest. These tables will exist in the database 'df_trusted_${env}`.

The data fields will be:
- reference_id: This will be the security_id provided by the user in the REST API, it will be integers that map to a stock ticker.
- business_unit: This will be the team requesting the change (via the REST API). Some examples of business_unit is AE, or CMF
- package_name: This will be a job name, something that the User provides in their request. This is just some string to further group the requests.
- request_date: This will be the date the request was made e.g. 2024-05-16

Both of them will contain the same data. But, unlike security_of_interest_pit, security_of_interest_latest will only contain the latest
(business_unit, package_name) pair when querying via Athena. 

For example: If User wants the following:
```
reference_id(s): [123, 456]
business_unit: AE
package_name: job_1
request_date: [Implicitly calculated to be today]
```
Only to change their mind a few minutes later to only be:
```
reference_id(s): [123]
business_unit: AE
package_name: job_1
request_date: [Implicitly calculated to be today]
```
My Athena queries would return the latest one with only 123 in the reference_id list for that (business_unit, package_name).

The high level "flow" will go as follows:

1) User will interact with our REST API, which will expose a POST endpoint. The user will indicate the business_unit, the package_name, and a list of
reference_id
2) Our REST API will take that payload and write that into S3 so that its available for query in AWS Athena at those tables.

Some other things to note, the business_unit will/must correspond with the user that makes the call, they refer to the team they belong to. So only a user who is part of the AE team can make a call associated with the business_unit so im not sure if this is better in the endpoint URL or as part of the payload.

Each business_unit will probably have thousands of package_name and there may be hundreds of reference_id per package_name, so i imagine there will be millions of rows.

While business_units must already exist (e.g. AE is an existing business_unit so its valid but XYZ isn't and would fail), this endpoint would be responsible for creating new package_name and the package_name will contain some list of reference_ids.

To start: How would you design the endpoint? The endpoint should be robust and should be able to accept multiple package_names, and each package_name should support multiple reference_ids

I want something that is stable for the long-term that is extendable, and generalizable

============
