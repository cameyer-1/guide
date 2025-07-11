## **Chapter 2: The Building Blocks: Core Concepts**

A successful system architect is not defined by their knowledge of the trendiest new database. They are defined by their deep, first-principles understanding of the fundamental components of distributed systems. Knowing *what* a load balancer is is trivial. Knowing the trade-offs between Layer 4 and Layer 7 load balancing and which to apply in a given scenario is what distinguishes a senior engineer.

This chapter details these core building blocks. Mastery is not memorization. It is understanding the operating characteristics, trade-offs, and failure modes of each component. This is your toolkit. Do not attempt to build a house without knowing the difference between a hammer and a wrench.

---

### **Load Balancing**

At its simplest, a load balancer distributes incoming network traffic across multiple backend servers. Its purpose is to prevent any single server from becoming a bottleneck, thereby improving application availability and responsiveness. Saying "we'll put a load balancer in front of the servers" is an incomplete thought. The critical question is: *what kind*?

**Layer 4 (L4) vs. Layer 7 (L7) Load Balancing**

*   **Layer 4 (Transport Layer):** An L4 load balancer operates at the network transport layer (TCP, UDP). It makes routing decisions based on information from the first few packets in the network flow (source/destination IP addresses and ports).
    *   **Mechanism:** It directs network packets to a specific server without inspecting the packet's content.
    *   **Pros:** Extremely fast, high throughput, and computationally inexpensive.
    *   **Cons:** Not application-aware. It doesn't know about HTTP headers, URLs, or cookies. It cannot make routing decisions based on the *type* of request.
    *   **Use Case:** Ideal for simple, high-volume traffic distribution where content-based routing is not required.

*   **Layer 7 (Application Layer):** An L7 load balancer operates at the application layer. It can inspect the content of the request itself (e.g., HTTP headers, URL paths, cookies).
    *   **Mechanism:** It terminates the network connection, reads the message, makes an intelligent routing decision based on the content, and then initiates a new connection to the selected backend server.
    *   **Pros:** Intelligent routing. Can route `/api/video` requests to video-processing servers and `/api/user` to user-management servers. Enables sticky sessions (directing a user's requests to the same server via cookies). Can handle SSL termination, freeing up backend servers from this computationally expensive task.
    *   **Cons:** Slower than L4 due to the need to inspect packets. More computationally expensive.
    *   **Trade-off:** You sacrifice some raw performance and increase complexity for significantly more intelligent traffic management. For almost all modern web applications, L7 is the standard choice.

**Common Algorithms**
*   **Round Robin:** Distributes requests sequentially across the pool of servers. Simple but inefficient, as it doesn't account for server load or health.
*   **Least Connections:** Directs traffic to the server with the fewest active connections. More intelligent than Round Robin, as it accounts for requests that may take longer to process.
*   **IP Hash:** Computes a hash of the client's IP address to determine which server receives the request. This ensures a given user will consistently hit the same server, which can be useful but is inferior to proper sticky sessions via L7 cookies.

---

### **Caching Strategies**

A cache is a high-speed data storage layer that stores a subset of transient data. The primary purpose of a cache is to reduce latency for read requests and decrease the load on slower, more expensive backend resources like a primary database. The question is not *if* you should cache, but *how*.

*   **Cache-Aside (Lazy Loading):** This is the most common caching strategy.
    *   **Flow:**
        1.  The application looks for an entry in the cache.
        2.  **Cache Hit:** If found, the data is returned from the cache.
        3.  **Cache Miss:** If not found, the application reads the data from the database, stores a copy in the cache, and then returns it.
    *   **Pros:** Resilient against cache failures (the application can still get data from the DB). The cache only holds data that is actually requested.
    *   **Cons:** Introduces a latency penalty on the first request for any given piece of data (the cache miss). Data in the cache can become stale if the source of truth (the database) is updated directly.

*   **Read-Through:** A strategy where the cache itself is responsible for fetching data from the database.
    *   **Flow:** The application queries the cache. If the cache misses, the cache itself queries the database, stores the result, and returns it to the application.
    *   **Pros:** Simplifies application code; the application treats the cache as the main data source.
    *   **Cons:** Less common in general-purpose caches; often a feature of more specialized or library-specific cache providers.

*   **Write-Through:**
    *   **Flow:** When the application writes data, it writes it to the cache *and* the database simultaneously (or the cache writes it to the DB). The operation is only considered complete when both are successful.
    *   **Pros:** Ensures data in the cache is never stale. High data consistency.
    *   **Cons:** Introduces write latency. Every write must go to both the cache and the database, making it slower than a write-back strategy. The cache can fill up with data that is written but rarely read.

*   **Write-Back (or Write-Behind):**
    *   **Flow:** The application writes directly to the cache. The cache acknowledges the write immediately and then asynchronously flushes the data to the database in the background after some delay.
    *   **Pros:** Extremely low-latency writes. Absorbs write spikes very well.
    *   **Cons:** Risk of data loss. If the cache fails before the data is persisted to the database, the data is lost forever. More complex to implement correctly.
    *   **Trade-off:** This is a choice for write-heavy systems where write performance is critical and a small risk of data loss upon failure is acceptable.

---

### **Database Deep Dive: SQL vs. NoSQL**

"Use a NoSQL database" is not an engineering decision; it is a sign of shallow thinking. The choice between a relational (SQL) and non-relational (NoSQL) database is one of the most fundamental architectural decisions, dictated entirely by the data model, query patterns, and consistency requirements defined in Phase 1.

**Relational (SQL) - e.g., PostgreSQL, MySQL**
*   **Model:** Data is stored in tables with predefined schemas and relationships. Enforces structure and referential integrity.
*   **Core Strength:** ACID transactions (Atomicity, Consistency, Isolation, Durability). This guarantees that transactions are processed reliably.
*   **When to use it:**
    *   When data integrity and strong consistency are non-negotiable (e.g., financial systems, e-commerce transactions, booking systems).
    *   When your data is highly structured and relational, requiring complex queries with JOINS.

**Non-Relational (NoSQL)**
NoSQL is a broad category, not a single technology. The choice must be specific.
*   **Model:** Flexible schemas. Generally optimized for horizontal scalability and high throughput.
*   **Core Strength:** High availability and massive scalability, often at the cost of guaranteed consistency (per the CAP theorem).
*   **Categories & Use Cases:**
    1.  **Key-Value Store (e.g., Redis, DynamoDB):** Stores data as a simple key-value pair.
        *   **Use Case:** The absolute simplest, fastest model. Ideal for caching, session management, user preferences, and real-time leaderboards.
    2.  **Document Store (e.g., MongoDB, Couchbase):** Stores data in JSON-like documents. Each document can have its own structure.
        *   **Use Case:** Excellent for semi-structured data like user profiles, content management, and product catalogs where attributes for items vary.
    3.  **Wide-Column Store (e.g., Cassandra, HBase):** Stores data in tables with rows and a dynamic number of columns. Optimized for queries over large datasets.
        *   **Use Case:** Ideal for massive-scale, write-heavy applications like analytics, logging, and time-series data.
    4.  **Graph Database (e.g., Neo4j, Amazon Neptune):** Stores data in nodes and edges, modeling relationships directly.
        *   **Use Case:** Built specifically for data where relationships are the primary feature, such as social networks, fraud detection, and recommendation engines.

**Universal Database Concepts**
*   **Indexes:** A data structure (like a B-Tree) that improves the speed of data retrieval operations on a database table at the cost of increased writes and storage space. Essential for performant queries.
*   **Replication:** The process of copying data from a primary database to one or more replica databases. Its primary purposes are to improve read throughput (by routing read queries to replicas) and provide high availability (a replica can be promoted to primary if the original fails).
*   **Sharding (Partitioning):** The process of breaking up a very large database into smaller, more manageable pieces called shards. Sharding is the primary method for scaling *writes* horizontally. A poor choice of shard key can lead to unbalanced shards ("hot spots") and defeat the purpose.

---

### **Message Queues & Event-Driven Architecture**

Message queues are a core component for building asynchronous, decoupled systems. They allow services to communicate without being directly connected or even available at the same time.

*   **Mechanism:** A producer service writes a message (a packet of data) to a queue. One or more consumer services subscribe to that queue, receive the message, and process it at their own pace.
*   **Key Benefits:**
    *   **Decoupling:** The producer doesn't know or care which service consumes the message.
    *   **Asynchronicity:** The producer can fire and forget the message, moving on to other tasks without waiting for a response.
    *   **Load Leveling:** A queue can absorb sudden spikes in traffic, protecting downstream services from being overloaded. Consumers can process the backlog steadily.

**Common Technologies & Their Trade-offs**
*   **RabbitMQ:** A mature message broker that supports complex routing protocols (AMQP). Excellent for intricate workflows where messages need to be routed based on various rules.
*   **Apache Kafka:** Technically a distributed streaming platform, not just a queue. It behaves like a durable, persistent log. Producers append events, and consumers can read from any point in that log.
    *   **Use Case:** Built for extreme-high throughput and fault tolerance. Ideal for event sourcing, log aggregation, and stream processing at massive scale (e.g., tracking user clicks on a website).
    *   **Trade-off:** Higher operational complexity than simpler queues, but offers unparalleled scale and durability.
*   **Amazon SQS / Google Pub/Sub:** Managed cloud services. They remove the operational burden of running your own broker. The trade-off is less control and potential for higher cost at extreme scale compared to a self-hosted solution.

---

### **Content Delivery Network (CDN)**

A CDN is a globally distributed network of proxy servers that caches content closer to end-users. When a user requests a file, the request is redirected to the nearest CDN server (edge server), which serves the file from its cache.

*   **Primary Use Case:** Serving static assets like images, videos, CSS, and JavaScript files.
*   **Advanced Use Case:** Caching dynamic API responses for a short duration.
*   **Benefits:**
    1.  **Lower Latency:** Users get content from a geographically closer server, reducing round-trip time.
    2.  **Reduced Origin Load:** The CDN absorbs a huge percentage of traffic, protecting your origin servers.
*   **Trade-off:** Cost. Also, cache invalidation can be a challenge. If a file is updated on your origin server, you need a strategy to tell the CDN to purge its old copy.

---

### **The CAP Theorem in Practice**

The CAP theorem states that it is impossible for a distributed data store to simultaneously provide more than two of the following three guarantees:
*   **Consistency (C):** Every read receives the most recent write or an error. All nodes in the cluster see the same data at the same time.
*   **Availability (A):** Every request receives a (non-error) response, without the guarantee that it contains the most recent write.
*   **Partition Tolerance (P):** The system continues to operate despite an arbitrary number of messages being dropped (or delayed) by the network between nodes.

In any real-world distributed system, network partitions are a fact of life. Therefore, **you must design for Partition Tolerance (P)**. This means the real trade-off in system design is always between Consistency and Availability (C vs. A).

*   **CP (Consistent & Partition Tolerant):** When a partition occurs, the system will sacrifice availability to prevent inconsistency. It may return an error or time out until the partition is resolved.
    *   **Example:** A bank transfer. You would rather the system be unavailable than allow a transaction that results in an incorrect balance.
*   **AP (Available & Partition Tolerant):** When a partition occurs, the system will remain available but may return stale data.
    *   **Example:** A social media "like" count. It is acceptable for a user to see a slightly outdated count if it means the site remains responsive. Eventual consistency is sufficient.

---

### **Consistent Hashing**

In a distributed system, a common task is to map a key (like a user ID or cache key) to a server. A naive approach is `server = hash(key) % N`, where N is the number of servers.

*   **The Problem:** What happens when you add or remove a server (N changes to N+1 or N-1)? Nearly every key in the system will map to a new server. This causes a catastrophic storm of cache misses or data rebalancing. It's an unscalable approach.
*   **The Solution: Consistent Hashing.**
    *   **Mechanism:** Imagine a ring or circle representing the hash value space (e.g., 0 to 2^32-1). Both servers and keys are hashed and placed onto this ring. To find which server a key belongs to, you start at the key's position on the ring and move clockwise until you find a server.
    *   **Benefit:** When a server is added or removed, it only affects the keys in its immediate neighborhood on the ring. The vast majority of keys remain mapped to their original servers, minimizing data movement and cache invalidation. This is essential for building scalable caches and databases like DynamoDB and Cassandra.

---

### **Proxies: Forward vs. Reverse**

A proxy is an intermediary server that sits between a client and a destination server. The distinction between a forward and reverse proxy is critical and often confused.

*   **Forward Proxy:** A proxy used by the **client**. It acts on behalf of a client (or group of clients).
    *   **Position:** Sits "in front of" the client.
    *   **Use Case:** Common in corporate networks to filter or log outbound traffic, or to bypass geo-restrictions. From the destination server's perspective, the traffic appears to come from the proxy server, not the original client.

*   **Reverse Proxy:** A proxy used by the **server**. It acts on behalf of a server (or pool of servers).
    *   **Position:** Sits "in front of" the server(s).
    *   **Use Case:** This is the most common proxy type in system design. Load balancers, API gateways, and SSL termination servers are all forms of reverse proxies. They receive requests from clients, forward them to the appropriate backend server, and return the server's response. From the client's perspective, it is simply talking to a single server and is unaware of the backend infrastructure.