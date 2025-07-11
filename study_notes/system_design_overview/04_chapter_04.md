## **Chapter 4: The E-Commerce & Services Tier**

This chapter transitions from the largely virtual world of social media to systems that interface with real-world constraints: physical location, finite inventory, and complex state management. The problems in this tier—ride-sharing, ticket booking, and web crawling—introduce a new set of critical challenges. Success here is measured not just by scalability, but by transactional integrity, concurrency control, and the management of high-volume, real-time data streams. An error in a social feed is an inconvenience; an error in a booking system results in a direct financial or physical-world failure. The required level of engineering rigor is therefore substantially higher.

---

### **Design a Ride-Sharing Service (e.g., Uber, Lyft)**

This problem tests a candidate's ability to integrate real-time geospatial data, manage stateful transactions, and handle high-volume, concurrent communication between multiple types of clients (riders and drivers).

**1. Requirements and Scoping**

*   **Functional Requirements (MVP):**
    *   A rider can request a ride from their current location to a destination.
    *   Nearby drivers are notified of the ride request.
    *   A driver can accept the request. Once accepted, no other driver can accept it.
    *   The rider and driver can see each other's live location during the trip.
    *   The ride has distinct states: `requested`, `accepted`, `in_progress`, `completed`, `cancelled`.
    *   **Explicitly Defer:** Payments, driver ratings, chat functionality, surge pricing.
*   **Non-Functional Requirements:**
    *   **High Availability:** The service must be operational; downtime loses rides.
    *   **Low Latency:** Driver location updates and ride requests must be processed in near real-time. Matching a rider to a driver should be fast (< 5 seconds).
    *   **Consistency:** Strong consistency is required for the ride's state (a ride cannot be accepted by two drivers). Eventual consistency is acceptable for driver location updates.
    *   **Scalability:** Must support millions of active users, with thousands of location updates per second.

**2. API Design**

This system is inherently event-driven and requires more than a simple request/response API. Persistent connections are key.

*   **Driver Client:**
    *   `POST /api/v1/locations` (sends frequent location updates: `lat`, `lon`).
    *   `POST /api/v1/rides/{ride_id}/accept`
    *   **Listens on a persistent connection (WebSocket/gRPC) for ride offers.**
*   **Rider Client:**
    *   `POST /api/v1/rides` (request a ride: `start_lat`, `start_lon`, `end_lat`, `end_lon`).
    *   `GET /api/v1/rides/{ride_id}` (poll for ride status and driver location).

**3. High-Level Architecture**

A microservices architecture is the most logical fit.

`Driver/Rider Clients -> API Gateway -> [Location Service, Matching Service, Ride Service]`

These services interact with each other and with specialized data stores. The core challenge is the interaction between them.

**4. Deep Dive on Core Components**

**a) Location Service: Handling Driver Pings**
This is a massive-scale write ingestion problem. Thousands of drivers update their location every few seconds.

*   **Suboptimal Design:** Have the `Location Service` write every ping directly to a main relational database. The database would be overwhelmed by write IOPS and become an immediate bottleneck.
*   **Optimal Design: Decouple and Batch**
    1.  The `Location Service` receives location pings (`driver_id`, `lat`, `lon`) via the API Gateway.
    2.  Instead of writing to a database, it publishes this event to a high-throughput message stream like **Apache Kafka**. The topic can be partitioned by `city_id` or geographical region.
    3.  A separate consumer service reads from this stream.
    4.  The consumer updates a data store optimized for fast geospatial queries. The canonical choice here is **Redis with its Geospatial features**.
    *   **Redis Command:** `GEOADD driver_locations <longitude> <latitude> <driver_id>`. This stores the driver's location in a sorted set, indexed for geospatial queries.
    *   **Justification:** This architecture is built for write-heavy workloads. Kafka acts as a durable buffer, smoothing out traffic spikes. Redis provides extremely low-latency lookups for the "find nearby drivers" problem. The main ride database is protected from this high-volume stream.

**b) Matching Service: Finding Nearby Drivers**
When a rider requests a trip, this service performs the core matching logic.

1.  The `Ride Service` receives a `POST /rides` request. It creates a ride with a `requested` status in the main database and then asks the `Matching Service` to find a driver.
2.  The `Matching Service` queries the geospatial index in Redis.
    *   **Redis Command:** `GEORADIUS driver_locations <rider_longitude> <rider_latitude> 5 km WITHCOORD WITHDIST`. This command efficiently returns all drivers within a 5km radius.
3.  The service filters this list for `available` drivers (availability status could also be stored in Redis or another fast cache).
4.  For the N closest drivers, the `Matching Service` pushes a "ride offer" notification to them via a **push notification service** (like Firebase Cloud Messaging) or a persistent WebSocket connection.

**c) Ride Service: Managing State Transitions**
This is the transactional heart of the system. It owns the state of a ride.

*   **Database Choice:** A **relational database (e.g., PostgreSQL)** is the correct choice for storing the `rides` and `users` tables. The ACID properties are non-negotiable here.
*   **Concurrency Control:** When a driver accepts a ride (`POST /rides/{ride_id}/accept`), this service must ensure atomicity.
    *   The `Ride Service` starts a database transaction.
    *   It updates the state of the ride from `requested` to `accepted` and assigns the `driver_id`. Crucially, it must use a condition to ensure the ride is still available: `UPDATE rides SET status = 'accepted', driver_id = ? WHERE ride_id = ? AND status = 'requested'`.
    *   If this update affects 1 row, the transaction commits, and a success message is sent back.
    *   If it affects 0 rows (meaning another driver already accepted it), the transaction rolls back, and an error is returned to the driver. This prevents the double-booking race condition.

---

### **Design a Ticket Booking System (e.g., Ticketmaster)**

This problem's primary challenge is extreme concurrency control. When tickets for a popular event go on sale, thousands of users attempt to reserve a small, finite set of items simultaneously. The design must handle a massive traffic spike while guaranteeing that a seat is never sold twice.

**1. Requirements and Scoping**

*   **Functional Requirements (MVP):**
    *   A user can view the seating chart for an event.
    *   A user can select one or more available seats.
    *   Upon selection, the seats are held for that user for a short duration (e.g., 10 minutes).
    *   The user must complete the purchase within this window to confirm the booking.
*   **Non-Functional Requirements:**
    *   **Strong Consistency:** The state of a seat (`available`, `held`, `sold`) must be absolutely consistent. No double-selling.
    *   **Spike Tolerance:** The system must survive a massive, predictable traffic spike when an event goes on sale.

**2. API Design**

*   `GET /api/v1/events/{event_id}/seats` - Returns the state of all seats.
*   `POST /api/v1/holds` - Request a temporary hold on specific seats.
    *   Body: `{"event_id": ..., "seat_ids": ["A1", "A2"]}`
    *   Response: `{"hold_id": "...", "expires_at": "..."}`
*   `POST /api/v1/bookings` - Confirm a purchase using a valid hold.
    *   Body: `{"hold_id": ..., "payment_details": ...}`

**3. Architecture: Handling the Spike and the Race Condition**

**a) Level 1: The Virtual Waiting Room**
The backend database cannot handle millions of users hitting it simultaneously. The first line of defense is to not let them in.

*   **Mechanism:** When tickets go on sale, users are not sent directly to the booking page. They are first sent to a holding page and placed in a **virtual queue**.
*   **Implementation:** A service like RabbitMQ or a custom Redis-based queue can manage this. A `Queue Service` dequeues users at a fixed rate (e.g., 1000 users per minute) that the backend systems are provisioned to handle.
*   **Benefit:** This transforms a massive, damaging spike into a flat, predictable load. It protects the core transactional system from being overwhelmed.

**b) Level 2: The Hold Pattern**
Once a user is let in, you must prevent them from fighting over seats. Locking database rows (`SELECT FOR UPDATE`) is one option, but can lead to poor performance under load. A better, more scalable pattern is to manage holds explicitly.

1.  **Inventory Data Model:** The state of each seat is stored in a highly consistent database (PostgreSQL is a good choice). A table like `seat_inventory (seat_id, event_id, status, hold_id, hold_expires_at)`.
2.  **Creating a Hold:** When a user POSTs to `/holds` for seats `["A1", "A2"]`:
    *   The `Booking Service` starts a transaction.
    *   It checks the status of seats "A1" and "A2". It must use a pessimistic lock here to be absolutely safe: `SELECT * FROM seat_inventory WHERE seat_id IN ('A1', 'A2') AND event_id = ? FOR UPDATE;`.
    *   If all seats are `available`, it updates their status to `held`, sets a `hold_id`, and an `expires_at` timestamp (e.g., now + 10 minutes).
    *   The transaction is committed.
    *   If any seat is not `available`, the transaction is rolled back, and an error is returned.
3.  **Confirming or Expiring the Hold:**
    *   If the user completes payment (`POST /bookings`), the status for the held seats is updated from `held` to `sold`.
    *   A separate, asynchronous **background job** (a janitor service) continuously scans the database for holds where `hold_expires_at` is in the past. It then resets the status of those seats back to `available`, freeing them up for other users.

**Trade-off:** This design prioritizes consistency and system stability over raw performance during a conflict. The waiting room makes the user experience predictable, and the hold pattern ensures data integrity for the core business logic.

---

### **Design a Web Crawler**

This is a quintessential distributed systems problem that tests understanding of queueing, state management for massive datasets, politeness policies, and fault tolerance.

**1. Requirements and Scoping**

*   **Functional Requirements:**
    *   Given a starting set of seed URLs, the crawler must visit these pages.
    *   It must parse the HTML to extract all hyperlinks.
    *   It must add these new, undiscovered URLs to a list of URLs to visit.
    *   It should store the raw HTML content of visited pages.
*   **Non-Functional Requirements:**
    *   **Scalability:** Must be able to crawl billions of pages.
    *   **Robustness:** Must be resilient to component failures, bad HTML, and unresponsive servers.
    *   **Politeness:** Must respect `robots.txt` and not overwhelm any single host with rapid-fire requests.

**2. High-Level Architecture: The Crawl Loop**

A web crawler is fundamentally a graph traversal algorithm running on a planetary scale.

`URL Frontier -> Pool of Crawler Workers -> HTML Parser -> Link Extractor -> URL Frontier`

**3. Deep Dive on Core Components**

**a) The URL Frontier**
This is the brain of the crawler. It's not a single component, but a service managing two critical pieces of state: what to crawl next and what has already been crawled.

*   **To-Visit Queue:** This contains the URLs to be crawled. Given the scale (billions of URLs), this cannot be an in-memory list. It must be a persistent, distributed message queue system. It's often implemented as a set of queues prioritized by heuristics like PageRank or update frequency.
*   **Visited Set:** To avoid re-crawling pages and getting stuck in loops, the crawler must know which URLs it has already processed.
    *   **Problem:** Storing billions of URLs in a database and querying it for every single extracted link is too slow and expensive.
    *   **Solution: Bloom Filter + KV Store.**
        1.  A **Bloom Filter** is a probabilistic, space-efficient data structure. Before hitting the database, check if the URL is in the Bloom Filter.
        2.  If the Bloom Filter says "no", the URL is definitely new. Add it to the To-Visit queue and a persistent Key-Value store (the source of truth).
        3.  If the Bloom Filter says "yes", the URL *might* have been seen before (false positive). Now, perform a definitive check against the slower but accurate KV store.
    *   **Justification:** This two-tier check saves an enormous number of expensive database lookups, as the vast majority of extracted links will have been seen before.

**b) The Crawler Workers**
These are stateless worker processes that execute the main crawl loop.

1.  **Get Work:** The worker pulls a batch of URLs from the `URL Frontier`'s queue.
2.  **DNS Resolution:** Resolves the URL's hostname to an IP address. This is a common bottleneck; results must be cached heavily.
3.  **Politeness Check:**
    *   The worker must fetch and parse the `robots.txt` file for the hostname. These rules dictating what can and cannot be crawled **must be obeyed**.
    *   The rules should be cached per hostname to avoid refetching on every request.
    *   The worker must also enforce a rate limit (e.g., only one request to `example.com` per second) to avoid being banned. This is often managed by a central scheduler mapping hostnames to worker queues.
4.  **Fetch Content:** Makes the HTTP GET request and downloads the page's raw HTML.
5.  **Store Content:** The raw HTML is written to a bulk, low-cost storage system. A distributed object store like **Amazon S3** or HDFS is the ideal choice.
6.  **Parse and Extract Links:** The HTML is passed to a parser which extracts all `href` attributes.
7.  **Submit New Links:** These extracted, normalized URLs are sent back to the `URL Frontier` service to be added to the work queue (after passing through the Visited Set check).

**c) Key Challenges and Scalability**
*   **Duplicate Content:** Different URLs can have identical content. Hashing the content of each page and storing the hashes can detect these duplicates.
*   **Crawler Traps:** Poorly designed websites can generate infinite URLs (e.g., calendars). This is mitigated by setting a max depth for URL paths and using heuristics to detect generated content.
*   **Sharding:** The entire system must be sharded. The `URL Frontier`'s queues and KV stores can be sharded by hostname to ensure politeness and locality. The `Crawler Workers` are stateless and can be scaled horizontally.