# HTTP Endpoint Designs

This is a guide for building production-grade, enterprise-level APIs.

First, we establish the bedrock. These are the non-negotiable principles. If you violate these, your API is fundamentally flawed, and you will create pain for your client engineers, your future self, and your operations team.

---

## **Part 1: The Bedrock - Core Principles of Resource-Oriented Design**

This is the foundation upon which everything else is built. It's based on REST, but more importantly, it's based on the principles of HTTP itself, which is the most successful distributed system protocol ever created. Don't fight it; leverage it.

#### **1.1 Resources are Nouns. HTTP Methods are Verbs.**

This is the most fundamental rule. Your API endpoints identify **things**, not **actions**.

*   A **Resource** is an object or a concept: a user, a product, an order, a financial transaction.
*   Your URL (Uniform Resource *Identifier*) gives that thing a unique name.
*   The HTTP Method (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) is the action you perform on that thing.

**INCORRECT (Action-oriented):**
```
POST /createUser
GET /getUsers
POST /updateUser
POST /deleteUser
```
This is a disaster. It's brittle, unpredictable, and forces the client to memorize a unique endpoint for every single action. It treats the web like a function library (RPC), ignoring the resource-oriented nature of HTTP.

**CORRECT (Resource-oriented):**
```
/users
/users/{userId}
```
This is it. This is your entire surface area for managing users. How do you perform actions? You use the correct verb.

#### **1.2 Master Your HTTP Methods (The Verbs)**

Each method has a specific, globally understood meaning. Using them correctly tells the client, and any intermediate layer (caches, CDNs, proxies), exactly what to expect. The most critical concepts here are **Safety** and **Idempotency**.

*   **Safe:** The request can be made without changing the state of the resource. `GET`, `HEAD`, `OPTIONS` are safe.
*   **Idempotent:** Making the same request N times has the same effect as making it once.

Let's be precise:

*   **`GET`**: Retrieve a resource or a collection of resources.
    *   `GET /users` → Returns a list of users.
    *   `GET /users/{userId}` → Returns a single user.
    *   **Properties**: Safe and Idempotent.

*   **`POST`**: Create a *new* resource as a subordinate of a collection.
    *   `POST /users` → Creates a new user. The request body contains the user's data. The server will generate the ID.
    *   **Properties**: Neither Safe nor Idempotent. Sending the same `POST` request twice will create two distinct users.

*   **`PUT`**: Completely replace an existing resource. The client specifies the full resource representation.
    *   `PUT /users/{userId}` → Replaces the entire user object identified by `{userId}` with the data in the request body. If `{userId}` doesn't exist, you can choose to create it (`upsert` behavior), or return a `404 Not Found`. Be consistent.
    *   **Properties**: Idempotent. Sending the same `PUT` request N times results in the same final state. Not Safe.

*   **`PATCH`**: Partially update an existing resource.
    *   `PATCH /users/{userId}` → Updates only the fields specified in the request body. For example, to change only the user's email.
    *   **Properties**: Neither Safe nor inherently Idempotent. (e.g., `PATCH` to increment a value is not idempotent).

*   **`DELETE`**: Remove a resource.
    *   `DELETE /users/{userId}` → Deletes the user.
    *   **Properties**: Idempotent. Deleting something a second time doesn't change the state (it's already gone). Not Safe.

#### **1.3 Speak the Language of HTTP Status Codes**

Your response must tell the client exactly what happened. Don't just send `200 OK` for everything. Precision here is the mark of a professional.

**`2xx` - Success:**
*   **`200 OK`**: Standard success response for `GET`, `PUT`, `PATCH`. The response body usually contains the resource.
*   **`201 Created`**: The resource was successfully created. Use this for `POST`. A critical best practice is to include a `Location` header in the response pointing to the URL of the newly created resource (e.g., `Location: /api/v1/users/123`).
*   **`204 No Content`**: The server fulfilled the request but there is no content to send back. This is the perfect response for a successful `DELETE` operation.

**`4xx` - Client Error (It's *their* fault):**
*   **`400 Bad Request`**: The request was malformed. The syntax is wrong, a required field is missing, etc. The response body *must* contain a clear explanation of what is wrong.
*   **`401 Unauthorized`**: The client tried to access a protected resource without providing authentication credentials. They need to log in.
*   **`403 Forbidden`**: The client is authenticated, but they do not have permission to perform the requested action. The distinction between 401 and 403 is crucial.
*   **`404 Not Found`**: The resource at the specified URL does not exist.
*   **`422 Unprocessable Entity`**: The request syntax was correct (`400` is not appropriate), but the server couldn't process it due to semantic errors. For example, a field value is out of range or violates a business rule.

**`5xx` - Server Error (It's *our* fault):**
*   **`500 Internal Server Error`**: A generic, catch-all error. Something went wrong on our end, and we don't have a more specific error to show. Never leak stack traces here. Just a generic error message and an error ID for tracking.

#### **1.4 Design a Clean, Predictable URL Structure**

*   **Path for Hierarchy:** Use the URL path to define the resource and its hierarchy.
    *   `GET /products/{productId}`
    *   `GET /users/{userId}/orders` (Get all orders for a specific user)
    *   `GET /users/{userId}/orders/{orderId}` (Get a specific order for a specific user)
    *   **Warning**: Avoid deep nesting (more than 2 levels). `.../orders/{orderId}/items/{itemId}/reviews/{reviewId}` is a nightmare. If you need that level of detail, use query parameters or consider a GraphQL approach.

*   **Query for Filtering/Sorting/Pagination:** Use query parameters for anything that modifies the view of a resource *collection*, but not the resource itself.
    *   Filtering: `GET /products?status=available&category=electronics`
    *   Sorting: `GET /products?sort=-price` (minus sign for descending)
    *   Pagination: `GET /products?page=2&limit=50`

---

This covers the absolute foundation. If an engineer I'm interviewing can't articulate and defend these principles, the interview is over. This is the minimum bar for entry.

Let me know when you're ready to proceed. Next, we'll discuss the hallmarks of a professional API: **payload design, versioning, security fundamentals, and robust handling of collections.**

---

Let's move beyond the basics into what separates a merely functional API from a professional, robust, and scalable one. This is about building an API that engineers won't hate using and that won't crumble under its own weight.

## **Part 2: Hallmarks of a Professional API**

Once the bedrock is in place, you must focus on the developer experience (DX) for your clients and the operational health of your service. These are not optional extras; they are critical for building systems that last.

#### **2.1 Payload Design: The Contract is in the JSON**

The request and response bodies are your primary contract with the client. Sloppiness here leads to constant bugs and confusion.

*   **Always Use JSON:** For REST APIs, this is the non-negotiable standard. It's universally supported, human-readable, and performant enough for almost all use cases. Do not invent your own format. Do not use XML unless you have a legacy or regulatory requirement.
*   **Consistency is King:** Choose a casing convention and enforce it everywhere.
    *   **JSON Body:** Use `camelCase` for keys (`"userId"`, `"firstName"`). This is the native convention for JavaScript, the language of the web, and makes life easier for front-end developers. `snake_case` is also acceptable if your backend language's ecosystem prefers it, but *pick one*. A mix of `user_id` and `firstName` in the same object is a sign of extreme sloppiness.
    *   **HTTP Headers:** The standard is `kebab-case` (`Content-Type`, `X-Request-ID`). Follow it.
*   **Use Precise, Standard Data Formats:** Ambiguity is your enemy.
    *   **Dates and Times:** Always use **ISO 8601** format, and always in **UTC** (`YYYY-MM-DDTHH:MM:SSZ`). Example: `"2023-10-27T10:00:00Z"`. This is an unambiguous, machine-readable standard. Sending Unix timestamps is less readable, and sending strings like "October 27, 2023" is an unforgivable error that introduces parsing nightmares and timezone bugs.
    *   **Enums:** Use strings, not integers. `{"status": "processing"}` is infinitely better than `{"status": 2}`. String-based enums are self-documenting and resilient. If you add a new enum value, old clients might not understand it, but they won't misinterpret it as another value.
*   **Design Excellent Error Payloads:** A `4xx` or `5xx` status code is not enough. The response body must help the client developer solve the problem. A good error payload is a lifeline.
    **INSUFFICIENT:**
    ```
    "Invalid input."
    ```
    **PROFESSIONAL:**
    ```json
    {
      "error": {
        "type": "VALIDATION_ERROR",
        "message": "Input validation failed.",
        "details": [
          {
            "field": "email",
            "issue": "Must be a valid email address."
          },
          {
            "field": "password",
            "issue": "Must be at least 12 characters long."
          }
        ]
      }
    }
    ```
    This tells the client *exactly* what's wrong, which fields are affected, and provides a stable error `type` they can code against.

#### **2.2 Masterful Handling of Collections**

Returning a list of resources (`GET /products`) seems simple, but it's a minefield for performance and usability. Never return an unbounded list of results.

*   **Always Paginate:** Your service will crash if `GET /products` tries to serialize millions of records. Pagination is mandatory.
    *   **Method 1: Offset/Limit Pagination:** (`/products?page=2&limit=50`). It's easy to implement but has a fatal flaw: it performs terribly on large datasets. Asking the database for `OFFSET 1000000 LIMIT 50` forces it to scan and discard a million rows. This is unacceptable at scale. It's also unstable; if a new item is added to page 1 while the user is viewing page 2, their pages will be skewed on refresh.
    *   **Method 2: Cursor-based Pagination (Keyset Pagination):** This is the **correct** approach for high-performance systems. The API returns a block of results and an opaque `cursor` pointing to the next page.
        ```json
        // Response for GET /products?limit=50
        {
          "data": [ ... 50 products ... ],
          "pagination": {
            "next_cursor": "aW_8xq_LPT..." // Opaque token
          }
        }
        ```
        The client's next request is simply `GET /products?limit=50&cursor=aW_8xq_LPT...`. The cursor internally encodes the `WHERE` clause (e.g., `WHERE created_at > 'timestamp_of_last_item' AND id > 'id_of_last_item'`), which is extremely fast for a database to execute with an index. It's stateless and stable.

*   **Structure Collection Responses:** Never return a raw JSON array (`[...]`) as the top-level response. This makes it impossible to add metadata later, like pagination info, without breaking the client. Always wrap your collections in an object.
    ```json
    {
      "data": [ ... results ... ],
      "pagination": { ... } // Or other metadata
    }
    ```

*   **Filtering and Sorting:** Provide capabilities but control them tightly.
    *   Use clear query parameters: `GET /products?status=active&sort=-price` (minus for descending).
    *   **Crucially:** Do not allow filtering or sorting on arbitrary fields. This is a massive security and performance vulnerability. Only expose filtering and sorting for specific, indexed columns in your database. Whitelist allowed parameters explicitly.

#### **2.3 API Versioning: Plan for Evolution**

Your API will change. If you don't have a versioning strategy, you will either never improve your API or constantly break your clients.

*   **The Best Strategy: URI Versioning.** It's explicit, clear, and easy to route.
    `/api/v1/users`
    `/api/v2/users`
    This is the most common and practical approach. Proxies, gateways, and even developers can immediately see which version of the API they are interacting with.

*   **When to Create a New Version (`v2`)?** Only for **breaking changes**.
    *   **Breaking change:** Removing a field from a response, renaming a field, changing a data type (`integer` to `string`), fundamentally altering authentication or authorization logic.
    *   **Non-breaking change:** Adding a new, optional field to a response, adding a new optional parameter to a request, adding a new endpoint. These do *not* require a version bump. Design your clients to be resilient to new fields they don't recognize.

*   **Avoid Overly "Academic" Versioning:** Some argue for versioning in the `Accept` header (`Accept: application/vnd.myapi.v2+json`). While technically pure, it's less practical. It's harder to test in a browser, less obvious in logs, and more difficult for routing infrastructure to handle. For 99% of use cases, path versioning is superior.

#### **2.4 Security is Job Zero**

Designing an API without considering security from the first minute is professional malpractice.

*   **Use TLS Everywhere (HTTPS):** No exceptions. Any unencrypted HTTP traffic is a security breach waiting to happen, exposing data and credentials to man-in-the-middle attacks.
*   **Authentication (Who are you?):** Use a robust, standard mechanism. For most modern APIs, this means **OAuth 2.0 Bearer Tokens**. The client sends an `Authorization: Bearer <token>` header with every request to a protected endpoint. Don't invent your own authentication scheme.
*   **Authorization (What can you do?):** Authentication is not enough. For every single request, your service must perform an authorization check. If a user requests `GET /orders/{orderId}`, you must verify that the authenticated user actually owns that order or has admin privileges. Failure to check this on every nested resource (`/users/{id}/...`) is the source of countless data breaches.

---

We've now covered the contract, the structure for handling data at scale, and the plans for evolution and security. These principles turn a basic API into a professional one.

Next, we will discuss advanced, operational concerns: **idempotency for write operations, rate limiting, and knowing when to break the REST pattern entirely for RPC and bulk operations.**

Now we move from design theory into the operational realities of running a high-stakes system. These are the concepts that ensure your API is not just well-structured, but also resilient, scalable, and capable of handling the messy imperfections of the real world.

### **Part 3: Advanced Concepts for Production-Grade Systems**

These are the features that distinguish a system built to last from one that will fail under pressure or create untenable operational burdens.

#### **3.1 Idempotency for Write Operations: Surviving Network Chaos**

The network is unreliable. A client might send a request, but the connection times out before they receive a response. Did the request succeed? Should they retry?

For a `GET`, `PUT`, or `DELETE`, this is fine because they are idempotent. But what about `POST`? Retrying a `POST /payments` request could result in a customer being charged twice. This is unacceptable.

The solution is to allow clients to enforce idempotency on non-idempotent requests.

*   **The Mechanism: The `Idempotency-Key` Header**
    This is a design pattern perfected by services like Stripe. The client generates a unique key (e.g., a UUID) for every *operation* it wants to execute exactly once.
    `POST /transfers`
    `Idempotency-Key: a8f2d7a9-a9a3-4b6e-a239-24757475f479`

*   **Server-Side Logic:**
    1.  When a request with an `Idempotency-Key` arrives, the server first checks a short-term cache (like Redis) to see if it has ever processed this key before.
    2.  **If the key is new:** The server processes the request as normal. Before sending the response, it **saves the HTTP status code and response body** to the cache, using the idempotency key as the cache key. A TTL of 24 hours is typical.
    3.  **If the key has been seen:** The server **does not** re-execute the business logic. It immediately retrieves the saved response from the cache and sends it back to the client.

*   **Result:** The client can safely retry the request with the same `Idempotency-Key` for hours. If the original succeeded, they'll get the original success response. If it failed with a validation error, they'll get the same validation error back. They are protected from accidentally creating duplicate resources. This transforms a risky `POST` into a safe, retryable operation, dramatically improving system reliability.

#### **3.2 Rate Limiting and Throttling: Protecting Your Service**

Your API is a finite resource. Without protection, a single misconfigured client or malicious actor can flood your service with requests, overwhelming your servers and causing a denial of service for all legitimate users.

*   **Principle:** You are responsible for keeping your service stable. Rate limiting is not optional.
*   **Strategy: Per-Client Throttling.** Identify clients by their API key or authenticated user ID. Limiting by IP address is a weak fallback, as many users can share one IP (e.g., behind a corporate NAT).
*   **Algorithm: Token Bucket.** This is the industry-standard algorithm. Each client has a "bucket" of tokens that refills at a constant rate. Each request costs one token.
    *   This gracefully handles bursts: a client can use up their entire bucket quickly.
    *   It enforces a long-term average rate: once the bucket is empty, they are limited to the refill rate.
    *   It's superior to a simple "fixed window" counter, which can allow double the intended traffic if a burst occurs at the boundary of two windows.

*   **Communicating Limits to the Client:** Don't just reject them; tell them how to behave. When a client exceeds their limit, respond with `429 Too Many Requests` and include these standard headers:
    *   `Retry-After`: The number of seconds the client should wait before making a new request.
    *   `X-RateLimit-Limit`: The total number of requests allowed per window.
    *   `X-RateLimit-Remaining`: The number of requests left in the current window.
    *   `X-RateLimit-Reset`: The UTC epoch timestamp for when the window resets.

    This turns your rate limiter from a blunt instrument into a predictable part of the API contract, allowing clients to build more robust and adaptive integrations.

#### **3.3 When to Break the Rules: Pragmatism over Dogma**

A true senior engineer knows that REST is a guide, not a straitjacket. Sometimes, forcing a complex business operation into a pure CRUD model makes things *worse*. The goal is clarity and effectiveness, not dogmatic purity.

*   **Scenario 1: Complex Actions (RPC-style Endpoints)**
    Some operations are not CRUD actions. They are complex workflows.
    *   "Publishing" a product (runs checks, changes state, sends notifications).
    *   "Suspending" a user (terminates sessions, revokes tokens, logs the action).
    *   "Escalating" a support ticket.

    **Amateur Approach:** Shoehorn it into a `PATCH`. `PATCH /products/{id}` with `{"status": "published"}`. This hides the complexity and side-effects. The handler for `PATCH` becomes a bloated `if/else` block, trying to figure out what operation is *really* happening.

    **Professional Approach: Use an RPC-style verb scoped to the resource.**
    `POST /products/{productId}:publish`
    `POST /users/{userId}:suspend`

    We use `POST` because these are state-changing, non-idempotent operations. The URL is still rooted in the resource (`/products/{productId}`), but the custom action (`:publish`) explicitly declares the intent. This makes the API contract crystal clear and allows you to build a dedicated, focused controller for that complex logic. This is the pattern advocated by Google's influential API Design Guide.

*   **Scenario 2: Bulk Operations**
    A client needs to update the stock count for 2,000 products.

    **Naive Approach:** Tell the client to make 2,000 individual `PATCH` requests. This is a performance disaster. The combined latency of 2,000 HTTP round trips is enormous, it generates huge server load, and it has no transactional integrity—if request #1,500 fails, the first 1,499 are still committed.

    **Professional Approach: Build a dedicated bulk endpoint.**
    `POST /products:batchUpdate`

    The request body would contain a list of operations to perform:
    ```json
    {
      "updates": [
        { "productId": "prod_123", "patch": { "stockCount": 50 } },
        { "productId": "prod_456", "patch": { "status": "discontinued" } }
      ]
    }
    ```
    This single request allows the backend to perform the updates far more efficiently (e.g., within a single database transaction). The response should indicate the success or failure of each sub-operation, providing clarity on partial failures. This is a deliberate trade-off of RESTful purity for a massive gain in performance and reliability.

---

We have now covered the advanced, battle-tested techniques required to run an API at scale. These concepts address reliability, fairness, and the practical need to adapt your design to solve complex business problems efficiently.

The final domain would cover the API lifecycle: **documentation, observability (logging, metrics, tracing), and a clear deprecation strategy.**

We've designed the API. We've fortified it for production. Now we must address the final, critical piece of the puzzle: managing the API as a living product. An API without documentation, observability, and a plan for its own death is a liability. This is what ensures your system is maintainable and comprehensible in the long term.

---

## **Part 4: The API Lifecycle - From Birth to Deprecation**

An API that isn't understood can't be used correctly. An API that isn't observable can't be debugged. And an API that lives forever becomes a ball and chain on your architecture.

#### **4.1 Documentation is Not an Afterthought, It's Part of the Product**

If developers can't figure out how to use your API, you have failed. The goal is to generate documentation that is clear, interactive, and always up-to-date. Manual documentation in a Word document is a recipe for instant obsolescence.

*   **The Standard: OpenAPI Specification (formerly Swagger)**
    This is the industry-standard, language-agnostic interface description for REST APIs. You define your endpoints, parameters, request/response models, and status codes in a YAML or JSON file.

*   **Code-First vs. Design-First:**
    *   **Code-First:** You annotate your controllers and models directly in your code (e.g., using libraries like `swashbuckle` for C# or `springdoc` for Java). The OpenAPI spec is generated automatically at build time.
        *   **Pro:** The documentation is guaranteed to be in sync with the code.
        *   **Con:** Can clutter the code. Doesn't facilitate early feedback from stakeholders before implementation begins.
    *   **Design-First:** You write the OpenAPI YAML by hand *before* writing any code. This spec becomes the contract.
        *   **Pro:** Forces you to think through the API design up front. Client teams can start building mock servers and integrations based on the spec immediately.
        *   **Con:** Risk of drift between the spec and the final implementation if not managed carefully with automated contract testing.

    At places like Meta or Netflix, we often use a hybrid. A staff engineer might draft a Design-First spec to get alignment, and then the implementation team uses a Code-First approach that is validated against the original contract.

*   **What Makes Great Documentation:**
    *   **Interactivity:** The spec file can be used to generate interactive API portals (e.g., Swagger UI, Redoc) where developers can read about endpoints and **make live API calls** directly from the browser. This is invaluable.
    *   **Clear Examples:** For every endpoint, show a complete request body and a complete response body for both success and error cases.
    *   **Authentication Explained:** Provide a clear, step-by-step guide on how to acquire and use authentication tokens.
    *   **Explain Business Logic:** Don't just list parameters. Explain *why* a field exists. What are the business rules governing `status`? What side effects does calling `DELETE /users/{id}` have (e.g., "This performs a soft delete and will also cancel all pending orders for this user.")?

#### **4.2 Observability: If You Can't See It, You Can't Fix It**

When things go wrong—and they will—you need to be able to answer three questions instantly: What broke? Why did it break? What was the impact? Observability is the key. It consists of three pillars.

*   **1. Logging:**
    *   **Use Structured Logs:** Don't just print strings. Log JSON objects. A log line like `"User 123 failed to update order 456"` is hard to parse. A structured log is machine-readable and searchable.
        ```json
        {"timestamp": "...", "level": "ERROR", "message": "Order update failed", "userId": 123, "orderId": 456, "reason": "Inventory not available"}
        ```
    *   **Log on Request/Response Boundaries:** Log the entry point and exit point of every API call. Include the method, path, status code, and latency. This is your baseline.
    *   **Do Not Log Sensitive Information:** Never, ever log PII, passwords, or authentication tokens in plaintext. This is a critical security and compliance requirement.

*   **2. Metrics:**
    *   Metrics are aggregated numerical data. They tell you the health of your system at a glance. They power your dashboards and alerts.
    *   **The Four Golden Signals (Google SRE):** This is the minimum set of metrics you must track for your API.
        1.  **Latency:** How long do requests take? (Track averages, but more importantly, p95 and p99 percentiles).
        2.  **Traffic:** How much demand is on your service? (Requests per second).
        3.  **Errors:** How often are requests failing? (Track the rate of `5xx` server errors and `4xx` client errors separately).
        4.  **Saturation:** How "full" is your service? (CPU utilization, memory usage, database connection pool size).
    *   Use a proper monitoring system like Prometheus or Datadog.

*   **3. Distributed Tracing:**
    *   In a microservices architecture, a single API call can trigger a chain reaction of calls across dozens of downstream services. When a request is slow or fails, how do you know which service is the culprit?
    *   **Distributed Tracing** solves this. A unique `trace-id` is generated at the entry point (your API gateway) and propagated through the `X-Request-ID` or `traceparent` header to every subsequent service call.
    *   Each service records "spans" (start time, end time) for its own work and logs them under that `trace-id`.
    *   Tools like Jaeger or Honeycomb can then reconstruct the entire call graph, showing you a waterfall diagram of the request's journey. This is indispensable for debugging latency issues in a complex system. It's the difference between guessing and knowing.

#### **4.3 The Deprecation Strategy: A Plan for Sunset**

The only thing worse than building a new API is being stuck supporting an old one forever. You must have a clear, well-communicated process for retiring old API versions.

*   **The Deprecation Process:**
    1.  **Announce:** When `v2` is launched, announce the deprecation timeline for `v1`. Communicate this in your developer documentation, changelogs, and directly to high-volume clients. A 6-12 month window is standard.
    2.  **Brownout:** As the deadline approaches, start to intentionally "brown out" the old version. For short periods (e.g., 10 minutes per day), start failing a percentage of requests to the old endpoint. This is a powerful way to get the attention of clients who have ignored your emails.
    3.  **Monitor:** Use your observability tooling. Track which clients are *still* calling the deprecated version. You should know exactly who will be impacted when you pull the plug.
    4.  **Remove:** On the scheduled date, remove the old version. The endpoints should now return a clear error (`410 Gone`). Your routing layer should no longer point to the old code.

---

### **Comprehensive Guide Summary**

*   **Part 1: The Bedrock.** Use nouns for resources and HTTP verbs for actions. Use standard status codes and a clean URL structure. Get this right or nothing else matters.
*   **Part 2: Professional Hallmarks.** Design clean, consistent JSON payloads. Master pagination with cursors. Version your API in the URL path. Build security in from day one with TLS, standard auth, and authorization checks.
*   **Part 3: Production-Grade Systems.** Implement idempotency for write operations to handle network failures. Use rate limiting to protect your service. Know when to pragmatically break REST rules for complex RPC-style actions and efficient bulk operations.
*   **Part 4: The API Lifecycle.** Automate documentation generation with OpenAPI. Instrument your service with logs, metrics, and distributed tracing. Have a clear, communicated plan for deprecating and removing old versions.