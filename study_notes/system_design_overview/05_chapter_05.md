## **Chapter 5: The Content & Data Tier**

The systems in this chapter are the bedrock of modern digital experiences. They manage the two most valuable assets of any large-scale service: its content and its data. Designing a video streaming platform requires mastering the entire content lifecycle, from computationally expensive ingestion to globally distributed, low-latency delivery. Designing a metrics system is about building the nervous system for an entire engineering organization, processing a firehose of operational data in real time. Finally, designing a distributed key-value store is a first-principles test of an engineer's understanding of data replication, consistency, and fault tolerance at the most fundamental level. Superficial answers in this domain are a clear signal of a candidate's lack of depth.

---

### **Design a Video Streaming Platform (e.g., Netflix, YouTube)**

A common mistake is to treat this problem as "design a file storage system." A video platform is not about storing and retrieving a single large file. It is a highly complex pipeline designed to deliver a smooth, uninterrupted viewing experience to millions of users on heterogeneous devices over unreliable networks. The core challenge is not storage; it's **preparation and delivery**.

**1. Requirements and Scoping**

*   **Functional Requirements (MVP):**
    *   A content owner can upload a video file.
    *   The platform processes the video so it can be played on various devices (web, mobile, smart TV).
    *   A user can search for a video and press play.
    *   The video playback must adapt to the user's changing network conditions.
*   **Non-Functional Requirements:**
    *   **High Availability:** The service must be highly available for both upload and playback.
    *   **Low Latency:** Playback must start quickly (< 2 seconds). Seeking within the video should be fast.
    *   **Scalability:** Must support millions of concurrent viewers and a massive catalog of videos.
    *   **Durability:** Uploaded video masters must never be lost.

**2. Architecture: A Tale of Two Pipelines**

The system must be split into two distinct, asynchronous pipelines: the **Content Ingestion Pipeline** and the **Content Delivery Pipeline**.

**I. The Content Ingestion & Processing Pipeline**

This is the offline, computationally-intensive process that happens after a creator uploads a raw video file.

`Raw Video File -> Ingestion Service -> Message Queue -> Transcoding Workers -> Distributed Object Store`

1.  **Ingestion Service:** A user uploads a high-quality master video file (e.g., a 50GB ProRes file) to an endpoint. This service performs initial validation (format checks, virus scans) and then uploads the raw file to a durable, low-cost **Distributed Object Store** (e.g., Amazon S3, Google Cloud Storage). This is our source of truth.
2.  **Triggering the Pipeline:** Upon successful upload, the Ingestion Service publishes a message to a **Message Queue** (e.g., SQS, Kafka). The message contains the video ID and the location of the raw file in the object store.
    *   **Justification:** Using a queue decouples the upload process from the extremely slow transcoding process. The user gets an immediate "Upload Successful, Processing Now" response. The queue allows us to scale the transcoding workers independently and provides resiliency against failures.
3.  **Transcoding Workers:** This is a farm of worker servers that consume from the queue. Their job is **transcoding**: the process of converting the raw video file into multiple different formats and bitrates.
    *   **Why is this critical?** You cannot serve a single 50GB file to a user on a 3G mobile connection. Transcoding creates multiple versions (renditions) of the video optimized for different scenarios.
    *   **What it does:**
        *   **Codec Conversion:** Converts the video from a professional codec (like ProRes) to highly compressed distribution codecs like **H.264 (AVC)**, **H.265 (HEVC)**, or **AV1**. Different devices support different codecs.
        *   **Container Conversion:** Puts the video and audio streams into a standard container format like **MP4**.
        *   **Adaptive Bitrate (ABR) Chunking:** This is the most important step. The worker takes each rendition (e.g., 1080p, 720p, 480p) and splits it into small, 2-10 second segments (e.g., `.ts` files). It also creates a **manifest file** (e.g., `.m3u8` for HLS, `.mpd` for MPEG-DASH). This manifest acts as a table of contents, telling the player where to find the chunks for each quality level.

4.  **Final Storage:** All generated chunks and manifest files are written back to the distributed object store, organized by video ID and resolution.

**II. The Content Delivery Pipeline**

This is the online, read-heavy system that serves the video to the user.

`Client Player <-> CDN <-> Object Store (Origin)`

1.  **Client Request:** A user presses play. Their client makes a request for the manifest file (e.g., `.../video123/master.m3u8`).
2.  **The Content Delivery Network (CDN):** This is non-negotiable. The video segments are not served directly from your S3 bucket. They are served from a **CDN**.
    *   The CDN caches the manifest and video chunks at edge locations around the world, physically close to users.
    *   When the user's player requests a chunk, it is served from the nearest CDN edge server, resulting in minimal latency. The CDN absorbs nearly 100% of the video traffic, protecting your origin.
3.  **Adaptive Bitrate Streaming (ABS) in Action:**
    *   The client player downloads the manifest file. The manifest tells it: "Here are the streams available: 480p at 800kbps, 720p at 2.5Mbps, 1080p at 5Mbps..."
    *   The player measures the user's current network bandwidth.
    *   It starts by requesting the lowest quality chunks.
    *   If it detects the network is fast enough, it will start requesting the higher bitrate (e.g., 720p) chunks for subsequent segments.
    *   If network conditions worsen, it will downgrade to a lower bitrate.
    *   **This adaptation happens seamlessly, chunk-by-chunk, and is the key to preventing buffering.**

**Metadata Database:** A separate database (e.g., Cassandra or DynamoDB) is used to store video metadata like title, description, user watch history (`user_id`, `video_id`, `last_watched_timestamp`), etc. This supports features like "Continue Watching."

---

### **Design a Metrics & Logging System**

Every engineering organization runs on data. A metrics and logging system is the centralized platform for collecting, storing, and analyzing operational data from every server, container, and application. Designing this requires handling a firehose of data and understanding the fundamentally different nature of logs and metrics. Lumping them together is a critical design flaw.

**1. Requirements and Scoping**

*   **Functional Requirements:**
    *   Collect structured metrics (e.g., CPU usage, request latency) from all hosts.
    *   Collect unstructured logs (e.g., application error messages) from all hosts.
    *   Allow users to query and visualize metrics on dashboards.
    *   Allow users to search and filter logs.
    *   Trigger alerts based on metric thresholds.
*   **Non-Functional Requirements:**
    *   **Extreme Write Scalability:** Must ingest millions of data points per second.
    *   **Query Performance:** Metric queries for dashboards must be fast (seconds). Log searches should be responsive.
    *   **Data Retention:** Metrics might be stored at high resolution for a short time (e.g., weeks) and downsampled for long-term storage. Logs are often retained for a compliance period (e.g., months).

**2. High-Level Architecture: Two Separate, Optimized Paths**

The core principle is to treat logs and metrics differently from the moment of ingestion.

`Hosts/Apps with Agents -> Collector/Gateway -> Message Bus (Kafka) -> [Log Path] & [Metrics Path]`

*   **Agents:** Lightweight agents (e.g., Fluentd, Prometheus Exporters) run on every host. They collect log files and scrape metrics endpoints.
*   **Collector/Gateway:** Agents send data to a central collection service. This service validates, enriches (e.g., adds `region`, `host_id` tags), and forwards the data.
*   **Message Bus (Kafka):** All incoming data is published to Kafka. This is the central buffer for the entire system. It protects the downstream storage systems from backpressure and allows different consumers to process the data independently. There should be separate topics for logs and metrics.

**3. Deep Dive on the Two Data Paths**

**a) The Logging Path**

*   **Characteristics:** Logs are unstructured text, often high in volume. The primary query pattern is full-text search and filtering by keywords or tags.
*   **Pipeline:** `Kafka -> Log Stasher/Processor -> Elasticsearch -> Kibana`
    1.  A consumer service (like Logstash) reads raw log messages from the Kafka `logs` topic.
    2.  It parses the unstructured text, extracting key fields (e.g., timestamp, severity, request_id).
    3.  This structured data is then written into a **Search Engine** like **Elasticsearch**.
    4.  **Why Elasticsearch?** It builds an inverted index on the log data, making full-text searches (`"error message contains 'NullPointerException'"`) extremely fast. This is its core competency.
    5.  Users interact with the data through a UI like **Kibana**, which provides powerful search and dashboarding capabilities on top of Elasticsearch.

**b) The Metrics Path**

*   **Characteristics:** Metrics are highly structured numerical data: (`metric_name`, `timestamp`, `value`, `set_of_tags`). The primary query pattern involves aggregations over time windows (`AVG(cpu.usage) over the last hour`).
*   **Pipeline:** `Kafka -> Metrics Processor -> Time-Series Database (TSDB) -> Grafana`
    1.  A consumer service reads structured metric data from the Kafka `metrics` topic.
    2.  This data is written into a **Time-Series Database (TSDB)** like Prometheus, M3DB, or InfluxDB.
    3.  **Why a TSDB?** Using a general-purpose database or even Elasticsearch for this is highly inefficient. TSDBs are purpose-built for time-series data:
        *   They use columnar storage, grouping data by metric name.
        *   They employ specialized compression algorithms (e.g., delta-of-delta encoding, Gorilla compression) that can reduce storage footprint by over 90% compared to row-based stores.
        *   They have query engines optimized for time-based range scans and aggregations.
    4.  Users interact with the data through a UI like **Grafana**, which excels at querying TSDBs and creating rich, time-based visualizations and dashboards.

**Alerting:** A separate alerting service (like Prometheus Alertmanager) periodically runs predefined queries against the TSDB. If a threshold is breached (`AVG(error_rate) > 5% for 10 minutes`), it fires an alert to an external system like PagerDuty or Slack.

---

### **Design a Distributed Key-Value Store (from scratch)**

This is an advanced problem. A candidate must demonstrate a deep understanding of partitioning, replication, consistency models, and failure handling. The answer should build up from a single node to a fully distributed, fault-tolerant system.

**1. Foundation: Single-Node KV Store**

At its heart, a KV store is a **hash map** in memory.
*   **APIs:** `PUT(key, value)`, `GET(key)`
*   **Persistence:** A purely in-memory store is useless, as data is lost on restart. We need persistence.
    1.  **Snapshots (e.g., Redis RDB):** Periodically, the entire hash map is written to a file on disk. This is efficient for reads but can lose data since the last snapshot.
    2.  **Append-Only Log (AOF):** Every write command (`PUT`) is appended to a log file. On restart, the log is replayed to reconstruct the in-memory state. This provides better durability but can lead to large log files. A combination of both is often used.

**2. Scaling Out: Distribution and Replication**

A single node has limited memory and is a single point of failure. We must distribute data across multiple nodes.

**a) Partitioning (Sharding)**

*   **Problem:** How do we decide which node stores which key?
*   **Solution: Consistent Hashing.**
    1.  Imagine a hash space (e.g., a ring from 0 to 2^32-1).
    2.  Each node is assigned a position (or multiple positions, using **virtual nodes**) on this ring.
    3.  To store a key, we `hash(key)` to find its position on the ring. We then walk clockwise along the ring to find the first node, which becomes the **coordinator node** for that key.
    4.  **Virtual Nodes (vnodes):** Instead of placing one token per node on the ring, we place many (e.g., 256) vnodes for each physical node. This ensures that when a node is added or removed, the workload is rebalanced much more evenly across the remaining nodes.

**b) Replication for High Availability and Durability**

*   **Problem:** If a node fails, its data becomes unavailable and could be lost forever.
*   **Solution: Replicate each partition onto N nodes** (typically N=3). The set of nodes responsible for a key is called its **preference list**.
*   **Placement Strategy:** The replication factor N must be larger than the number of simultaneous failures you want to tolerate. The nodes in a preference list must be placed in different failure domains (e.g., different racks, different Availability Zones) to prevent correlated failures.

**3. Read/Write Path and Consistency: The Quorum Model**

This is the core of the design. How do we ensure consistency across replicas?

*   Let **N** = Replication Factor (number of replicas).
*   Let **W** = Write Quorum. The number of replicas that must acknowledge a write before it is considered successful.
*   Let **R** = Read Quorum. The number of replicas that must respond to a read request.

The **Quorum Intersection Rule** (`W + R > N`) guarantees **strong consistency**.

*   **Write Path (`PUT(key, value)`):**
    1.  The client sends the request to the coordinator node for the key.
    2.  The coordinator sends the write request to all N replicas in the preference list.
    3.  The coordinator waits for at least **W** acknowledgements from the replicas.
    4.  Once W acks are received, the write is considered successful, and a response is sent to the client. If fewer than W replicas respond within a timeout, the write fails.

*   **Read Path (`GET(key)`):**
    1.  The client sends the request to the coordinator.
    2.  The coordinator sends read requests to all N replicas.
    3.  It waits for **R** responses.
    4.  Because `W + R > N`, the set of nodes a read contacts is guaranteed to overlap with the set of nodes a previous write contacted by at least one node. The coordinator can identify the most recent value (using version numbers) from the R responses and return that to the client.

*   **Trade-off Example (N=3):**
    *   **High Consistency (`W=3, R=2`):** `3+2 > 3`. This is a very safe configuration. Writes are slow (must wait for all replicas), but reads are faster and consistent. The system can tolerate 0 writer failures but 1 reader failure.
    *   **Balanced (`W=2, R=2`):** `2+2 > 3`. This is a common, balanced setting. It provides strong consistency while tolerating one replica failure for both reads and writes.
    *   **Fast Writes/Eventual Consistency (`W=1, R=1`):** `1+1 <= 3`. The `W+R > N` rule is violated. A write is acknowledged after just one replica saves it. Reads query just one replica. This is extremely fast but can return stale data if the queried replica has not yet received the latest write. This provides **eventual consistency**.

**Conflict Resolution during failures:** If a network partition causes different clients to write to different replicas of the same key, a conflict occurs. To resolve this, each value needs a version. A simple **Last-Write-Wins (LWW)** approach uses a timestamp, but this is susceptible to clock skew. A more robust solution is a **Vector Clock**, which can detect if versions are true descendants or if they are in conflict, allowing the application to decide how to merge the values.