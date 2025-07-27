### **Part 4: Applied Theory - Real-World Case Studies**

### **Chapter 12: Case Study: A Dating App (Hinge/Tinder)**

Let's get our hands dirty. Forget abstract theory. We're going to design the data model for a modern dating app. This is one of the most common system design prompts because it elegantly exposes every core challenge: high-volume reads for the feed, massive-volume writes for interactions (swipes), transactional logic for matches, and real-time communication for chat.

My experience at Citadel working on apps like Hinge and Tinder taught me one thing: a one-size-fits-all database approach will fail catastrophically at scale. We must break down the problem by its core functions and access patterns first. Only then can we choose the right tools.

#### **Step 1: Scoping and Identifying Core Entities**

First, let's define what we're building. Let's assume the core features are:
1.  User authentication and profile management (name, age, bio, photos).
2.  A feed of potential matches for the user to view.
3.  The ability to "like" or "pass" on a profile (the swipe).
4.  A "match" is created when two users "like" each other.
5.  A messaging system for matched users to communicate.

From these features, we can immediately identify our core entities:

*   **User:** Represents the person. Contains authentication info (email/phone, hashed password), account status (active, banned), and personal identifiers.
*   **Profile:** The public-facing information. Contains display name, age, bio, location, preferences, etc. A `User` has one `Profile`.
*   **Photo:** An image belonging to a profile. A `Profile` has many `Photos`.
*   **Swipe (or Like/Pass):** An action taken by one user on another. This is the atomic unit of interaction.
*   **Match:** Represents the mutual interest between two users. It enables communication.
*   **Message:** A text or media element sent between two matched users.

#### **Step 2: Defining the Critical Access Patterns**

This is the most important step. How the system *uses* the data will dictate our entire design.

1.  **User/Profile Management (Write-light, Read-heavy):**
    *   **Writes:** A user creates their profile once and updates it infrequently. These writes must be highly consistent. A user changing their bio must see that change reflected immediately.
    *   **Reads:** A user's own profile is read frequently. Another user's profile is read as part of the feed. Data is highly relational (profile links to photos, user, preferences).
    *   **Verdict:** This screams "Relational Database." The data is structured, relations are key, and we need strong consistency (ACID guarantees).

2.  **The Recommendation Feed (Read-very-heavy):**
    *   **Function:** For a given `user_id`, generate a list of other `profile_ids` to show. This involves complex logic: geographic proximity, age preferences, user behavior, ELO score, etc.
    *   **Access Pattern:** This is the most frequent read operation in the entire system. It's a complex `SELECT` query that needs to be fast. Running this against a live transactional database for millions of concurrent users is a recipe for disaster.
    *   **Verdict:** The feed itself isn't raw data; it's the *result* of a query. The actual profiles are in our relational DB, but the *list of candidates* should be generated offline by a recommendation service and stored in something fast for lookups, like a key-value store (e.g., Redis) or a pre-computed list.

3.  **The Swipe Action (Write-very-heavy):**
    *   **Function:** A user submits a "like" or "pass" on another user.
    *   **Access Pattern:** This is the highest volume write operation. At peak, this can be millions of writes per minute globally. Trying to shove this into a relational database with ACID transactions per swipe would grind it to a halt.
    *   **Consistency:** Eventual consistency is perfectly acceptable here. If a "like" takes a few hundred milliseconds or even a few seconds to register, no user will notice. Availability is king; the system must always be able to accept swipes.
    *   **Verdict:** This is a classic NoSQL use case. We need a write-optimized database that scales horizontally. A wide-column store like Apache Cassandra or ScyllaDB is the perfect tool for this job.

4.  **Matching and Messaging (Transactional Write, then Chat Stream):**
    *   **Matching:** A match is a critical event. It's triggered when User A likes User B, and we discover User B has already liked User A. This check-and-set operation needs to be atomic to avoid race conditions (e.g., both users matching each other simultaneously and creating two match records).
    *   **Messaging:** Once a match is made, the access pattern becomes a chat stream. Users fetch the message history for a given match and append new messages. Reads need to be chronologically sorted. Writes are frequent but scoped to a specific match.
    *   **Verdict:** This is a hybrid. The `Match` creation itself is transactional. The `Messages` are a time-series stream. We could model the `Match` table in our relational DB but offload the high volume of messages to a dedicated NoSQL database optimized for chat applications.

#### **Step 3: Designing the Data Model - The Hybrid Approach**

Based on the conflicting requirements above, a single database is the wrong choice. We will use polyglot persistence.

**1. System A: Core User & Profile Data (Relational)**

I'd choose PostgreSQL for its maturity, rich feature set (like PostGIS for geo-queries), and ACID compliance.

**Table: `users`**
```sql
user_id        UUID PRIMARY KEY
email          VARCHAR(255) UNIQUE NOT NULL
phone_hash     VARCHAR(255) UNIQUE
password_hash  VARCHAR(255) NOT NULL
created_at     TIMESTAMPTZ NOT NULL
status         VARCHAR(50) NOT NULL -- e.g., 'active', 'suspended'
```

**Table: `profiles`**
```sql
profile_id     UUID PRIMARY KEY
user_id        UUID UNIQUE NOT NULL REFERENCES users(user_id)
display_name   VARCHAR(100) NOT NULL
bio            TEXT
birth_date     DATE NOT NULL
gender         VARCHAR(50)
location       GEOGRAPHY(POINT, 4326) -- Using PostGIS for geo-queries
last_active_at TIMESTAMPTZ
-- ... plus other preference columns
```
*An index on `location` (GIST index) would be critical for "users near me" queries.*

**2. System B: The Swipe Ingestion Pipeline (NoSQL Wide-Column)**

I'd choose Apache Cassandra or ScyllaDB for its masterless architecture and incredible write throughput.

**Table: `swipes`**
The key here is the primary key design. We need to query for "who has swiped on me?" so the `target_user_id` should be the partition key.

```cql
CREATE TABLE swipes (
    target_user_id   UUID,      -- Who was swiped on (Partition Key)
    swiper_user_id   UUID,      -- Who did the swiping (Clustering Key)
    action           TEXT,      -- 'like' or 'pass'
    event_time       TIMESTAMP, -- Time of the swipe
    PRIMARY KEY ((target_user_id), swiper_user_id)
);
```
*   **Why this works:** When a user logs in, the "Match Service" can query this table with a single, efficient call: `SELECT swiper_user_id FROM swipes WHERE target_user_id = ? AND action = 'like'`. This fetches all the users who have liked the current user.

**3. System C: The Match & Chat System (Hybrid)**

This is where you show senior-level nuance.

**The `matches` Table (in PostgreSQL):**
We'll put the authoritative `Match` record back in our relational DB because creating a match is a transactional event that grants permissions.

```sql
CREATE TABLE matches (
    match_id         UUID PRIMARY KEY,
    user_a_id        UUID NOT NULL REFERENCES users(user_id),
    user_b_id        UUID NOT NULL REFERENCES users(user_id),
    created_at       TIMESTAMPTZ NOT NULL,
    status           VARCHAR(50), -- e.g., 'active', 'unmatched'
    UNIQUE (user_a_id, user_b_id)
);
```
*   **How it works:** After User A likes User B, the Match Service checks the Cassandra `swipes` table to see if B has liked A. If yes, it inserts a new row into this `matches` table *transactionally*. The `UNIQUE` constraint prevents duplicate matches.

**The `messages` Store (in NoSQL - DynamoDB/Cassandra):**
Chat messages can reach billions of records. Don't bloat your main PostgreSQL database with this. A dedicated message store is the correct architecture.

**Cassandra Table: `messages_by_match`**
```cql
CREATE TABLE messages_by_match (
    match_id      UUID,        -- The conversation (Partition Key)
    message_id    TIMEUUID,    -- Chronological, unique ID (Clustering Key)
    sender_id     UUID,
    content       TEXT,
    sent_at       TIMESTAMP,   -- Redundant but good for display
    PRIMARY KEY ((match_id), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);
```
*   **Why this works:** To load a chat, you query with `WHERE match_id = ?`. Because `message_id` is a `TIMEUUID` and the clustering order is `DESC`, you get the most recent messages first, perfect for displaying a chat window. This design is exceptionally scalable.

#### **Summary of Trade-offs and Final Architecture**

In an interview, I would conclude by sketching this out and explaining the flow:

1.  A **User** logs in, their profile is fetched from **PostgreSQL**.
2.  The **Recommendation Service** provides a list of profiles to show (the data for which is ultimately fetched from PostgreSQL).
3.  The User swipes. This write action is sent to a **Swipe Service** that logs it in **Cassandra**. This is fast and available.
4.  The **Match Service** asynchronously checks for new `like` events in Cassandra. If a mutual like is found (a match), it performs a transactional write to the `matches` table in **PostgreSQL** and sends notifications to the users.
5.  When matched users chat, the **Chat Service** authenticates against the `matches` table in PostgreSQL but reads/writes messages to the dedicated **Cassandra `messages` table**.

This hybrid, service-oriented data model is more complex to build initially, but it's the only way to solve the contradictory requirements of a modern dating app. It separates concerns, uses the right tool for each job, and is designed to scale to millions of users. This is the kind of robust, defensible design that demonstrates true system architecture competence.

### **Chapter 13: Case Study: A Media Streaming Service (Netflix)**

If the dating app case study was about handling high-volume transactions and interactions, Netflix is about modeling two things: a massive, complex library of content and an even more massive firehose of user behavior data. The scale is planetary. We're talking about hundreds of millions of users, hundreds of petabytes of video, and billions of user interaction events *per day*.

Anyone who suggests a single database for this system in an interview should be shown the door. It's not a single system. The only correct approach is to break it down into its logical sub-systems, analyze their completely different access patterns, and choose specialized data stores for each.

#### **Step 1: Scoping and Identifying Core Systems**

At a high level, a media streaming service performs these functions:
1.  **Account Management & Billing:** Handles user sign-ups, subscriptions, payment details, and profiles within an account (e.g., "Kids," "Dad").
2.  **Content Catalog & Metadata:** Manages the entire library of movies, series, episodes, genres, cast, and regional availability. This is the service's inventory.
3.  **Viewing History & Event Processing:** Tracks every single user interaction: play, pause, stop, seek, rating, browsing activity. This data is the fuel for personalization.
4.  **Personalization & Discovery:** Uses the viewing history to power features like "Continue Watching," "My List," and the iconic personalized row-based homepage.
5.  **Playback Service:** Manages device sessions and serves the actual video stream URLs from a CDN.

The core data entities that emerge are: `User`, `Account`, `SubscriptionPlan`, `Video` (a generic term for movies/episodes), `Series`, `Genre`, `Actor`, `ViewingEvent`, and `PlaybackState`.

#### **Step 2: Dissecting the Drastically Different Access Patterns**

Let's be direct. The access patterns for user billing and viewing history are so different they might as well be from different planets.

1.  **Account & Billing Data:**
    *   **Access Pattern:** High consistency is paramount. A user's subscription status must be transactionally accurate. Reads are frequent (on app load), but writes are infrequent (sign-up, plan change, monthly billing). The data is highly structured and relational.
    *   **Verdict:** This is the easiest decision. A classic relational database (SQL) like PostgreSQL or MySQL is the non-negotiable choice. ACID guarantees are a requirement, not a feature.

2.  **Content Catalog & Search:**
    *   **Access Pattern:** Very read-heavy. The data is updated infrequently (e.g., when Netflix licenses a new season), but read constantly by every user. The key challenge is serving these reads and supporting rich search queries (by title, genre, actor, description).
    *   **Source of Truth:** The metadata itself is relational (`Series` have many `Episodes`, `Videos` have many `Actors`, etc.).
    *   **The Problem:** Running full-text search and complex filter queries against your main transactional database for 200 million users is a terrible idea.
    *   **Verdict:** This calls for a hybrid approach. The *source of truth* for the catalog should be a relational database (PostgreSQL). However, this data is denormalized and pushed into a dedicated, read-optimized search index like **Elasticsearch** or OpenSearch. The application's search and browse APIs will query Elasticsearch, not the primary database.

3.  **The Viewing History Firehose:**
    *   **Access Pattern:** This is the most extreme workload in the system. It's almost entirely append-only writes. Every time a user plays, pauses, or stops a video, an event is generated. This is billions of events per day. Writes must be highly available; we'd rather drop an event than fail to accept it.
    *   **Consistency:** Eventual consistency is perfectly fine. If it takes a few minutes for a "view" to be incorporated into the recommendation model, nobody is harmed.
    *   **Verdict:** Storing this in a relational database is impossible. This is a job for a system designed for massive write throughput and horizontal scaling. We need a data pipeline. Events are pushed to a message queue like **Apache Kafka** and then consumed by multiple downstream systems, including a wide-column NoSQL database like **Apache Cassandra** for near-real-time queries and an offline data lake (**S3**) for batch analytics.

4.  **"Continue Watching" and Personalized Rows:**
    *   **Access Pattern:** This requires fast lookups of specific data. For "Continue Watching," we need the *latest playback timestamp* for a given `user_id` and `video_id`. For personalized rows ("Top Picks for Jacob"), a service pre-computes the list of video IDs and we need to store and retrieve that list quickly.
    *   **Writes:** Frequent updates to playback position.
    *   **Reads:** Very high volume, needs to be low-latency to render the homepage quickly.
    *   **Verdict:** This is a perfect use case for a Key-Value store. I'd use something like **DynamoDB** or Redis. The key is a composite of `user_id` and row-type (e.g., `user-123:continue-watching`), and the value is the list of video IDs and associated metadata (like playback position).

#### **Step 3: Designing the Polyglot Data Model Architecture**

Here's how we'd lay out the schemas for our chosen specialized databases.

**1. Accounts & Billing (PostgreSQL)**

Simple, normalized, and transactional.
**Table: `accounts`**
```sql
account_id        UUID PRIMARY KEY
primary_email     VARCHAR(255) UNIQUE NOT NULL
subscription_plan VARCHAR(50) NOT NULL
payment_method_id VARCHAR(100)
created_at        TIMESTAMPTZ NOT NULL
```
**Table: `users`** (Profiles within an account)
```sql
user_id        UUID PRIMARY KEY
account_id     UUID NOT NULL REFERENCES accounts(account_id)
display_name   VARCHAR(100) NOT NULL
user_type      VARCHAR(50) -- 'adult', 'kids'
```

**2. Catalog (PostgreSQL for Truth, Elasticsearch for Serving)**

*The Relational Source of Truth (PostgreSQL):*
```sql
-- videos table (for movies, episodes)
-- series table (with one-to-many to videos)
-- actors, genres tables
-- video_actors, video_genres (many-to-many link tables)
```
*The Denormalized Document (Elasticsearch):*
The ETL process would combine these tables into a single document per video to make searching fast.
```json
// Example document for a movie in Elasticsearch
{
  "video_id": "vid-abc-123",
  "type": "movie",
  "title": "The Matrix",
  "description": "A computer hacker learns...",
  "release_year": 1999,
  "duration_minutes": 136,
  "genres": ["Action", "Sci-Fi"],
  "actors": ["Keanu Reeves", "Laurence Fishburne"],
  "available_regions": ["US", "CA", "UK"]
}
```
Searching by any of these fields is now incredibly fast.

**3. Viewing History & Event Pipeline (Kafka + Cassandra + S3)**

This isn't just one database; it's a data flow.

**The Kafka Topic: `viewing_events`**
*   A single raw event looks like this:
    ```json
    { "user_id": "...", "video_id": "...", "event_type": "PLAY", "timestamp": "...", "playback_seconds": 0, "session_id": "..." }
    ```

**The Near-Real-Time Store (Cassandra)**
A consumer process reads from Kafka and writes to Cassandra for queries like "what has this user watched recently?"

**Table: `viewing_history_by_user`**
```cql
CREATE TABLE viewing_history_by_user (
    user_id          UUID,
    event_time       TIMESTAMP,
    video_id         UUID,
    event_type       TEXT,
    playback_seconds INT,
    PRIMARY KEY ((user_id), event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);
```
*   **Why it works:** Partitioning by `user_id` and clustering by `event_time` in descending order makes fetching the most recent viewing activity for any user a single, efficient read.

**The Long-Term Archive (Data Lake on S3)**
A second, separate consumer archives every raw event from Kafka into S3, partitioned by date. This becomes the immutable source of truth for training machine learning models with Spark or Flink.

**4. Personalized Homepage Data (DynamoDB)**

Fast lookups for the UI.

**Table: `homepage_rows`**
*   **Partition Key:** `user_id` (String)
*   **Sort Key:** `row_id` (String) e.g., "1:continue-watching", "2:top-picks", "3:trending-now"
*   **Attributes:** `row_title` (String), `video_list` (List of JSON objects)

*Example Item:*
```json
{
  "user_id": "usr-123",
  "row_id": "1:continue-watching",
  "row_title": "Continue Watching for Jacob",
  "video_list": [
    { "video_id": "vid-abc-123", "playback_seconds": 3610 },
    { "video_id": "vid-xyz-789", "playback_seconds": 125 }
  ]
}
```
Fetching a user's entire personalized homepage requires a single query: `Query WHERE PartitionKey = "usr-123"`. This is how you achieve millisecond-level latency for the main UI.

By breaking the system down and applying a specialized data model to each component, we've designed an architecture that can handle the immense and varied workloads of a global streaming service. This demonstrates a crucial senior engineering principle: don't force a single tool to solve multiple, distinct problems.

### **Chapter 14: Case Study: A Ride-Sharing App (Uber)**

We've covered user interaction at scale and massive content libraries. Now we tackle the real world, literally. A ride-sharing app is a system design problem about managing state and location in physical space, under the constraints of unreliable mobile networks. Having spent time at Uber, I can tell you the core challenges are less about big data analytics (though that exists) and more about high-concurrency, low-latency geospatial operations and bulletproof state management for the lifecycle of a trip.

Get this design wrong, and you have drivers dispatched to the wrong continent, riders getting charged for phantom trips, and a complete collapse of the marketplace.

#### **Step 1: Scoping and Identifying Core Systems & Entities**

First, let's nail down the critical path of the service:
1.  A Rider requests a ride from point A to point B.
2.  The system finds nearby available Drivers.
3.  A request is dispatched to one or more Drivers.
4.  A Driver accepts the trip.
5.  The system guides the Driver to the Rider, then both to the destination.
6.  The trip ends, payment is processed, and ratings are exchanged.

This workflow reveals our primary entities and the services that will own them:
*   **Entities:** `Rider` (user), `Driver` (a special user with a vehicle), `Vehicle`, `Trip` (the core stateful entity), `LocationUpdate`, `Payment`.
*   **Core Systems:**
    *   **User Service:** Manages Rider and Driver profiles, authentication, and ratings.
    *   **Dispatch Service (or "Supply"):** The brains. Tracks all online drivers' locations and finds the best match for a new ride request.
    *   **Trip Service:** The source of truth for a trip's lifecycle, from `requested` to `completed`.
    *   **Payments Service:** Handles all financial transactions.

#### **Step 2: Access Patterns - The Geospatial and State Machine Nightmare**

The data requirements here are fundamentally different from our previous case studies.

1.  **Driver Location Tracking (The Dispatch Problem):**
    *   **Access Pattern:** This is the most demanding component. You have thousands, even millions, of drivers constantly sending location updates (writes) every few seconds. Simultaneously, every new ride request triggers a read query: "find all available drivers within a 5km radius of this rider, right now."
    *   **Constraints:** This must be incredibly low-latency. A rider won't wait 30 seconds for the app to find a driver.
    *   **The Trap:** Do not use a standard relational database for this. A `SELECT * FROM drivers WHERE ST_DWithin(location, ?, 5000)` query on a table with millions of rapid updates will bring your system to its knees.
    *   **Verdict:** This requires a purpose-built solution. We need an in-memory database with first-class support for geospatial indexing. This isolates the high-volume, real-time location problem from everything else.

2.  **The Trip Lifecycle (The State Machine):**
    *   **Access Pattern:** The `Trip` entity is a long-lived object that transitions between states: `requested`, `accepted`, `driver_arrived`, `in_progress`, `completed`, `cancelled`. Each state transition is a critical business event and must be handled reliably.
    *   **Constraints:** We need strong consistency and atomicity for state changes. A trip cannot be `accepted` by two drivers. A trip cannot be `completed` and `cancelled` at the same time. The record of the trip is the source of truth for payment.
    *   **Verdict:** This is a perfect job for a robust, transactional relational database (SQL). It provides the ACID guarantees necessary to safely manage the state transitions.

3.  **User Profiles & Payments:**
    *   **Access Pattern:** Standard CRUD operations. Data is highly relational (drivers have vehicles, users have payment methods). Consistency is key for billing.
    *   **Verdict:** Just like in the Netflix case, this is a straightforward use case for a relational database like PostgreSQL.

4.  **Trip History & Receipts:**
    *   **Access Pattern:** Almost entirely read-heavy. A user might look at their trip history once a month. This query joins data from the trip, user, and driver tables.
    *   **Constraints:** Latency is not as critical as for live dispatch. Eventual consistency is acceptable.
    *   **Verdict:** While the primary `Trip` data lives in SQL, for serving historical queries, we can create a denormalized view in a document database (like MongoDB or DynamoDB) for faster, simpler lookups without burdening the primary transactional DB.

#### **Step 3: Designing the Data Model - Divide and Conquer**

Again, polyglot persistence isn't a choice; it's a necessity.

**1. The Dispatch Service's Geospatial Store (Redis or similar)**

We need speed. We'll use Redis for its in-memory performance and built-in GEO commands, which are based on a clever data structure called a Geohash. A geohash encodes a 2D latitude/longitude coordinate into a short string, where nearby points have similar prefixes.

*   **Data Structure:** A Redis Sorted Set (`GEOADD` command).
*   **Key:** `drivers_online:{geohash_prefix}` e.g., `drivers_online:9q8y` (geohash for San Francisco). This implicitly shards the data by region.
*   **Score:** The full Geohash integer representation.
*   **Value:** `driver_id`

**How it works:**
*   **Writes:** A driver's phone sends a location update. The backend calculates the geohash and executes a `GEOADD` on the corresponding key. This is an O(log N) operation, which is incredibly fast.
*   **Reads:** A rider requests a trip. The backend uses `GEORADIUS` or `GEOSEARCH` to query Redis for all driver IDs within a given radius of the rider's location. Redis handles the complex geo-query in memory at lightning speed.

**2. The Trip & User Services' Source of Truth (PostgreSQL)**

This is our rock of reliability.
**Table: `trips`**
```sql
trip_id            UUID PRIMARY KEY
rider_id           UUID NOT NULL REFERENCES users(user_id)
driver_id          UUID REFERENCES users(user_id) -- NULL until accepted
vehicle_id         UUID REFERENCES vehicles(vehicle_id)
status             VARCHAR(50) NOT NULL, -- 'requested', 'accepted', 'completed', etc.
origin_location    GEOGRAPHY(POINT, 4326) NOT NULL
destination_desc   TEXT
created_at         TIMESTAMPTZ NOT NULL
accepted_at        TIMESTAMPTZ
completed_at       TIMESTAMPTZ
-- We add an index on (driver_id, status) and (rider_id, status)
-- to quickly find active trips for a given person.
```
This table acts as the state machine. Every service involved in the trip's lifecycle (Dispatch, Notifications, Payments) interacts with this table to check and update its state transactionally.

**Tables: `users`, `vehicles`, `payments`**
These would be standard normalized tables in the same PostgreSQL database, managing profile data, vehicle registrations, and payment tokens with the expected referential integrity.

**3. The Trip History Archive (DynamoDB or MongoDB)**

After a trip reaches a terminal state (`completed` or `cancelled`), an asynchronous job reads the complete trip data from PostgreSQL, denormalizes it, and writes it to a document store optimized for easy reads.

**DynamoDB Table: `trip_receipts`**
*   **Partition Key:** `rider_id`
*   **Sort Key:** `completed_at` (as an ISO 8601 string or epoch)

*Example Item:*
```json
{
  "rider_id": "usr-abc-123",
  "completed_at": "2023-10-27T10:00:00Z",
  "trip_id": "trip-xyz-789",
  "driver": {
    "name": "Jane Doe",
    "rating": 4.9
  },
  "origin": "1 Infinite Loop, Cupertino, CA",
  "destination": "SFO Airport",
  "fare": 55.45,
  "currency": "USD"
}
```
Querying for a user's entire ride history is now a simple, fast `Query` operation on this table, which completely offloads that traffic from the critical transactional database.

By separating the ephemeral, high-volume geospatial data from the persistent, high-consistency stateful data, we create a system that is both scalable and reliable. The dispatch system can handle millions of location pings, while the trip service ensures that every single ride is accounted for and billed correctly. This is the only way to build a robust system that operates at the speed of the real world.
