## **Chapter 6: Advanced & Niche Problems**

The problems in this final design chapter are litmus tests. They are designed to probe the absolute boundary of a candidate's understanding of data structures, algorithms, and distributed coordination. A satisfactory answer to "Design Twitter" can be assembled from standard building blocks. The problems below cannot. They each contain a core, non-obvious challenge that requires a specific, principled solution. Providing a generic "web server + database" architecture here is an immediate signal of insufficient depth. Success requires moving beyond pattern-matching a blog post and into the realm of true architectural reasoning. This is where a senior staff engineer proves their worth.

---

### **Design a Proximity Server (e.g., "Find Nearby Friends")**

This is not a simple database query problem. It is a problem of indexing moving objects in a two-dimensional space at massive scale, where thousands of queries per second ask "who is near me?" while millions of objects are simultaneously reporting new locations.

**The Core Challenge:** Traditional B-tree indexes, which power most relational databases, are one-dimensional. They are catastrophically inefficient for geospatial queries because they have no concept of 2D spatial locality. A naive SQL query like `SELECT user FROM locations WHERE lat BETWEEN x1 AND x2 AND lon BETWEEN y1 AND y2` results in table scans or inefficient index usage that cannot possibly meet real-time latency requirements.

**Requirements and Constraints:**

*   **Functional:**
    *   The service must ingest frequent location updates for millions of objects (users, drivers, etc.).
    *   The service must respond to queries of the form: "Given a point (lat, lon) and a radius `R`, return all objects within that radius."
*   **Non-Functional:**
    *   **Low Latency:** Proximity queries must be extremely fast (<100ms P99).
    *   **High Update Throughput:** Must handle millions of location updates per minute.
    *   **Scalability:** Must scale to support hundreds of millions of objects.

**The Principled Approach: Grid Systems or Geohashing**

To solve this, you must transform the 2D problem into a 1D problem that can be indexed effectively.

*   **Method 1: Quadtree (and related Grid Systems):** Recursively subdivide the world map into four quadrants. If a quadrant contains more than a certain number of points, it is subdivided again. This creates a tree structure where a path down the tree narrows down to a smaller and smaller geographic area. This is powerful but can be complex to balance and distribute.

*   **Method 2: Geohashing (The more common interview choice):** This is a powerful and elegant heuristic.
    1.  Imagine the world map as a single bounding box.
    2.  Divide it in half by longitude. If a point is on the right, the first bit of its hash is `1`; if left, `0`.
    3.  Now divide the resulting rectangle by latitude. If the point is in the top half, the next bit is `1`; if bottom, `0`.
    4.  Continue this recursive subdivision, alternating between longitude and latitude cuts.
    5.  The resulting bits (`101101...`) are interwoven and then base32-encoded to create a short, indexable string—the **geohash**.
    *   **The Magic Property:** The longer two geohashes share a common prefix, the closer they are geographically. For example, the geohash `dpz8` represents a specific bounding box. All points within that box will share that prefix.

**System Deep Dive**

1.  **Ingestion Path:** A `Location Update Service` ingests pings (`object_id`, `lat`, `lon`). It should immediately publish this raw data to a Kafka topic partitioned by region for scalability.
2.  **Indexing Path:** A pool of `Geohash Indexer` workers consumes from Kafka. For each location update:
    *   It calculates the geohash to a fixed precision (e.g., 8 characters, which defines a ~150m x 150m box).
    *   It writes this data to a Key-Value store (like Redis or Cassandra). **The key is not the object_id.** The key is the `geohash_prefix`. The value is a set or list of `object_id`s within that grid square.
    *   `PUT(key="dpz8abcd", value.add("user_123"))`
3.  **Query Path:** A `Proximity Query Service` handles incoming search requests.
    *   For a given `(lat, lon)`, it calculates the corresponding geohash (e.g., `dpz8abcd`).
    *   It then queries the Key-Value store for that geohash *and its 8 neighboring geohashes*. This is critical to find objects just across a grid line.
    *   It retrieves the lists of `object_id`s from these 9 queries.
    *   **Post-Filtering:** The geohash method is a blunt instrument. It returns everything in the 9 grid boxes. The service must now perform an exact distance calculation (e.g., using the Haversine formula) on this much smaller candidate set to filter out any objects that are in the boxes but outside the query radius `R`.

**Trade-offs:** The choice of geohash precision is a fundamental trade-off. Longer hashes mean smaller, more precise grid squares. This reduces the number of false positives that need post-filtering, but it increases the chance that a query radius will span many more squares, requiring more initial lookups.

---

### **Design a Distributed Task Scheduler**

This system must reliably and accurately execute millions of tasks at specific future times. The core challenges are avoiding a single point of failure and designing a system that does not grind to a halt scanning a massive database of pending jobs.

**The Core Challenge:** A naive approach of storing tasks in a database and having a worker poll it with `SELECT * FROM tasks WHERE execution_time <= NOW()` fails at scale. This query becomes incredibly expensive and slow as the tasks table grows to millions or billions of rows. It puts constant, punishing load on the database for no reason. Furthermore, ensuring a task runs *exactly once* in a distributed environment where workers can fail is a non-trivial coordination problem.

**Requirements and Constraints:**

*   **Functional:**
    *   Users can schedule a task (e.g., an HTTP webhook) to be executed at a specific time.
    *   Users can list and delete pending tasks.
*   **Non-Functional:**
    *   **Reliability:** Tasks must execute at-least-once. The system should provide idempotency mechanisms to allow consumers to achieve exactly-once semantics.
    *   **Accuracy:** Tasks should execute within a few seconds of their scheduled time.
    *   **Scalability:** Must support scheduling millions of tasks.

**The Principled Approach: Hierarchical Timing Wheels**

A Timing Wheel is a data structure that provides a far more efficient way to manage pending timers than a sorted list or database query.

*   **Concept:** Imagine a circular array of 60 buckets. This is the "seconds" wheel. Each bucket represents a second. A task scheduled for 15 seconds from now is placed in the `(current_second + 15) % 60` bucket. A scheduler process has a single pointer that advances one bucket every second. When it enters a new bucket, it processes *all* tasks within it, without ever needing to scan the other 59.
*   **Hierarchical:** To handle tasks scheduled far in the future, you add more wheels. A second, 60-bucket "minutes" wheel. A third, 24-bucket "hours" wheel. A task for 2 hours, 30 minutes, 15 seconds from now is placed in the corresponding bucket on the hours wheel. When the "hours" pointer advances, it takes all tasks from its bucket and redistributes them into the appropriate "minutes" wheel buckets. This cascading "tick" is highly efficient.

**System Deep Dive**

1.  **Persistent Task Store:** All tasks are first written to a durable, horizontally scalable database like Cassandra or a sharded RDBMS. This is the source of truth. `task_id, owner_id, execution_time, payload, status (PENDING, LOCKED, DONE)`.
2.  **Scheduler Service (The Brains):**
    *   This is a stateful service. For fault tolerance, it runs in a small, active-passive cluster (e.g., 3 nodes). A service discovery tool like **ZooKeeper or etcd** is used for leader election. Only the leader is active.
    *   On startup, the leader loads tasks for the near future (e.g., the next few hours) from the database into its in-memory **Timing Wheel**.
3.  **The "Tick" and Firing:**
    *   Every second, the leader's timing wheel advances. It looks at the current bucket for any tasks that are due.
    *   For each due task, the Scheduler **does not execute it directly.** It simply publishes a message like `{"task_id": "xyz"}` to a **Message Queue** (e.g., SQS or RabbitMQ).
4.  **Executor Fleet (The Brawn):**
    *   This is a large, stateless pool of worker services that consume from the message queue.
    *   When an executor gets a `task_id`, it must acquire a lock on that task to ensure no other worker can run it. This is the key to achieving at-least-once execution.
    *   **Locking Mechanism:** `UPDATE tasks SET status = 'LOCKED', worker_id = ? WHERE task_id = ? AND status = 'PENDING'`. This atomic conditional update in the database serves as a distributed lock. If the update returns `1 row affected`, the worker has the lock and proceeds to execute the task. If it returns `0`, another worker beat it to the punch, and it can discard the message.
5.  **Failure Handling:** What if the leader of the Scheduler service crashes? ZooKeeper/etcd will detect the failure and trigger a leader election. A new node becomes the leader, loads tasks from the database, and resumes the "tick" from where the old one left off.

This design decouples scheduling logic from execution logic, allowing each to scale independently. The timing wheel avoids database load, and the transactional update prevents duplicate execution.

---

### **Design a Typeahead Suggestion Service**

The objective is to return ranked, relevant suggestions for a user's partial query with P99 latency in the tens of milliseconds. A database is not the right tool for the job.

**The Core Challenge:** An RDBMS using `LIKE 'prefix%'` is far too slow. It cannot be properly indexed for prefix searching and will collapse under the load of thousands of concurrent users typing. The system must also rank suggestions not just alphabetically, but by a relevance or popularity score, and it needs to do so almost instantly.

**The Principled Approach: A Weighted Trie (Prefix Tree)**

A Trie is a tree-like data structure purpose-built for prefix searches.

*   **Structure:** Each node in the Trie represents a character. A path from the root down to a node represents a prefix. For example, `root -> 'c' -> 'a' -> 'r'` represents the prefix "car".
*   **Weighted Trie:** To handle ranking, we store metadata at each node that represents a complete word. At the 'r' node in "car", we would store a list of top suggestions starting with "car" (e.g., "car", "cardigan", "carpet") and their associated popularity scores.

**System Deep Dive**

1.  **Offline Data Pipeline (Building the Trie):**
    *   The raw data for suggestions comes from historical search queries, document corpuses, or other sources.
    *   An **offline Spark or MapReduce job** runs periodically (e.g., daily) to process this data. It counts the frequency of queries, computes popularity scores, and builds the master **Trie data structure**.
    *   The output of this job is a serialized file (or set of files) representing the complete, compressed Trie. These files are stored in a durable location like S3.

2.  **Serving Tier (Delivering Suggestions):**
    *   A fleet of **`Trie Servers`** forms the core of the read path. These are very simple, lean services.
    *   On startup, each `Trie Server` downloads the latest Trie file from S3 and loads it entirely into its RAM. Memory access is orders of magnitude faster than disk or network access, which is key to low latency.
    *   The server exposes a single endpoint: `GET /suggest?q={prefix}`.
    *   When a request comes in, the server performs a simple traversal of the in-memory Trie:
        1.  It follows the path corresponding to the prefix characters (e.g., 'c', then 'a').
        2.  From the node representing the prefix, it retrieves the pre-computed, sorted list of top suggestions.
        3.  It returns this list as JSON. The entire operation takes only a few milliseconds.

3.  **Scaling and Updates:**
    *   **Scaling Reads:** The `Trie Servers` are stateless, so they can be scaled horizontally behind a load balancer to handle any amount of read traffic.
    *   **Sharding the Trie:** For an enormous dataset that won't fit on a single machine, the Trie can be sharded. A common strategy is to shard by the first character(s) of the query. A top-level router service would look at `q=car` and know to route it to the `a-d` shard.
    *   **Real-time Updates:** A daily build isn't enough for new, trending queries. This can be solved with a hybrid approach: augment the massive, static base Trie with a much smaller, in-memory "delta Trie" that is updated every few minutes with recent queries. The `Trie Server` would query both Tries and merge the results.