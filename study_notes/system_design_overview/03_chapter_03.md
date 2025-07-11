## **Chapter 3: The Social Media Tier**

The design problems in this chapter—URL shorteners, social feeds, and follow graphs—are canonical for a reason. They appear simple on the surface but conceal deep architectural challenges related to massive read throughput, high-volume writes (fan-out), and data modeling at scale. A candidate who can navigate these problems effectively demonstrates a practical understanding of caching, asynchronous processing, and database trade-offs. A candidate who offers a simplistic, naive solution reveals their inexperience. We will dissect these problems not to provide a template for memorization, but to illustrate the application of first-principles thinking under pressure.

---

### **Design a URL Shortener (e.g., TinyURL)**

This is often considered a warm-up problem, but its simplicity is deceptive. A robust design requires careful consideration of hash generation, collision resolution, and read/write path optimization. A failure to address these points is a failure in the interview.

**1. Requirements and Scoping**

*   **Functional Requirements:**
    *   Given a long URL, generate a shorter, unique alias (the "short URL").
    *   Given a short URL, redirect the user to the original long URL.
    *   Users should optionally be able to provide a custom alias.
    *   Short links should have an expiration time.
*   **Non-Functional Requirements:**
    *   **High Availability:** The service, particularly redirection, must be highly available.
    *   **Low Latency:** Redirection must be extremely fast (< 50ms P99).
    *   **Scalability:** Must handle millions of new URLs per day and billions of redirects. This implies a significant read-heavy workload (e.g., 100:1 read-to-write ratio). The shortened URLs must not be guessable.

**2. API Design**

A clean, RESTful API is expected.

*   `POST /api/v1/url`
    *   **Request Body:** `{"long_url": "...", "custom_alias": "..." (optional), "expires_in_days": 30 (optional)}`
    *   **Success Response (200):** `{"short_url": "http://short.ly/aBc123X"}`
    *   **Error Response (409 Conflict):** If the custom alias already exists.
*   `GET /{short_code}`
    *   **Success Response (301 Moved Permanently):** `Location: <original_long_url>`
    *   **Error Response (404 Not Found):** If the `short_code` does not exist.

**3. High-Level Design and Component Breakdown**

The core flow is straightforward. A write request goes through an application service to generate a code and store the mapping. A read request hits the service, looks up the code, and issues a redirect.

`Client -> Load Balancer (L7) -> URL Shortening Service (Stateless) -> Cache (Redis) -> Database`

**4. Deep Dive and Trade-offs**

This is where the critical thinking lies. We will analyze the write path (generation) and the read path (redirection).

**The Write Path: Generating the `short_code`**

*   **Naive Approach (and why it's wrong):** Use an auto-incrementing integer from a database sequence (e.g., ID `12345`) and base62-encode it (`[0-9a-zA-Z]`).
    *   **Why it's wrong:**
        1.  **It's predictable:** Competitors can guess your next URL and estimate your usage statistics. This is a business intelligence leak.
        2.  **It's a bottleneck:** A single sequence generator in a relational database is a centralized writer. It does not scale horizontally.

*   **A Better Approach: Hashing**
    1.  Take the `long_url` (optionally with a user-specific salt).
    2.  Apply a fast, non-cryptographic hash function like MD5 or MurmurHash to it, generating a 128-bit hash.
    3.  Take the first `k` characters of the base62-encoded hash. A 7-character code in base62 (`62^7`) gives ~3.5 trillion possibilities, sufficient to avoid collisions for a very long time.
    *   **Handling Collisions:** What if `hash(url_A)` and `hash(url_B)` produce the same 7-character short code? You *must* have a strategy for this.
        *   When generating a code, you **must** check if it already exists in the database.
        *   If it exists, you have two options:
            1.  **Check if the long URL matches:** If `short_code_xyz` already maps to the *same* long URL you're trying to shorten, simply return the existing `short_code_xyz`. This is an idempotent and efficient optimization.
            2.  **Generate a new code:** If `short_code_xyz` maps to a *different* long URL, a hash collision has occurred. Take a different portion of the hash, or apply a different hashing function with a different seed, and retry. This must be handled in a loop with a max retry limit. A failure here shows a lack of rigor.

**Database Schema**

The query patterns are extremely simple key-value lookups.
*   **Write:** `INSERT (short_code, long_url, expiration_date)`
*   **Read:** `SELECT long_url WHERE short_code = ?`

A relational database would work, but it's overkill. The ideal choice here is a **Key-Value Store** like DynamoDB or Redis.
*   **Schema:** `key: short_code`, `value: {long_url: "...", created_at: "...", expires_at: "..."}`
*   **Justification:** These databases are designed for massive horizontal scalability and extremely low-latency key-based lookups, which perfectly matches the non-functional requirements. A relational DB's overhead for transactions and complex joins is completely wasted here.

**The Read Path: High-Speed Redirection**

The read path must be blindingly fast. Waiting for a database query for every redirect is suboptimal.

1.  **Aggressive Caching:** The mapping of `short_code -> long_url` is a perfect candidate for caching. Use a distributed cache like Redis or Memcached.
2.  **Cache-Aside Strategy:**
    *   The `URL Shortening Service` receives a request for `GET /aBc123X`.
    *   It first queries Redis for the key `aBc123X`.
    *   **Cache Hit:** If found, it returns the 301 redirect immediately.
    *   **Cache Miss:** It queries the primary Key-Value store (DynamoDB), retrieves the `long_url`, populates the Redis cache with the result (setting a TTL is good practice), and then returns the redirect.

**5. Scaling and Optimizations**

*   **Database Scaling:** A Key-Value store like DynamoDB inherently handles sharding. If using a self-hosted solution, you'd shard the database using the `short_code` as the shard key, likely via consistent hashing.
*   **Expiration of Old Links:** A background job should periodically scan the database for entries where `expiration_date` has passed and delete them. This prevents indefinite data growth. For DynamoDB, using the TTL feature accomplishes this automatically.
*   **Geo-DNS:** For a global service, use Geo-DNS to direct users to the nearest regional deployment (e.g., a European user hits a European endpoint). Each region would have its own cache and could have its own read replica of the database, further reducing latency.

---

### **Design a Social Media Feed (e.g., Twitter/X)**

This is a classic read-heavy system design problem. The core challenge is efficiently generating a personalized feed for millions of users, each composed of posts from hundreds or thousands of followed accounts.

**1. Requirements and Scoping**

*   **Functional Requirements:**
    *   A user can post content (e.g., text, images).
    *   A user can follow other users.
    *   A user can view their personal timeline: a chronologically sorted list of posts from the people they follow.
*   **Non-Functional Requirements:**
    *   **Low Latency:** Generating the feed should be very fast (e.g., <200ms).
    *   **High Scalability:** Must support hundreds of millions of users and billions of posts. The system is extremely read-heavy (many more feed views than posts).
    *   **Eventual Consistency:** It is acceptable if a new post takes a few seconds to appear in the feeds of all followers.

**2. API Design**

*   `POST /api/v1/posts`
    *   **Request Body:** `{"user_id": "...", "content": "..."}`
    *   **Success Response (201):** `{"post_id": "...", "timestamp": "..."}`
*   `GET /api/v1/feed`
    *   **Request Parameters:** `?count=20&page_token=...` (for pagination)
    *   **Success Response (200):** `{"posts": [{"post_id": ..., "user_id": ..., "content": ..., "timestamp": ...}, ...], "next_page_token": "..."}`

**3. High-Level Design and The Core Trade-off: Pull vs. Push**

The central design choice is how the user's feed is generated.

*   **Approach 1: Pull / Fan-out on Read (The Naive Approach)**
    *   **Mechanism:** When a user requests their feed:
        1.  Fetch the list of all users they follow.
        2.  For each followed user, fetch their most recent posts.
        3.  Merge all these posts together in memory.
        4.  Sort the merged list by timestamp.
        5.  Return the top N results.
    *   **Why it Fails at Scale:** This is computationally expensive and slow. If a user follows 1000 people, a single feed load requires >1000 database queries. It creates a massive load storm on the read path and will never meet the latency requirement for an active user. **This approach is unacceptable for a large-scale system.**

*   **Approach 2: Push / Fan-out on Write (The Pre-computed Approach)**
    *   **Mechanism:** This approach pre-computes the timelines.
        1.  When a user `U` posts a new tweet `T`:
        2.  The system retrieves the list of all users who follow `U`.
        3.  For *each follower*, the system injects the post ID `T` into a data structure representing their personal timeline.
        4.  When a user requests their feed, the system simply reads this pre-computed list.
    *   **Pros:** The feed load is now a single, fast query to a pre-computed list. This is extremely efficient for the read path.
    *   **Cons:** The write path is now very expensive. A post from a user with 10 million followers requires 10 million writes. This can cause significant write latency and "hot spots". This is known as the **fan-out problem**.

**4. Deep Dive on the Push Model (Fan-out on Write)**

This is the superior architecture for a general-purpose feed.

`User -> Post Service -> Message Queue -> Fan-out Service -> Feed Cache (Redis)`

*   **Decoupling with a Message Queue:** The key to managing fan-out on write is to do it asynchronously.
    1.  The `Post Service` receives the user's post. It persists the post content to a `Posts` database (a wide-column store like Cassandra is a good fit for this immutable, time-series data).
    2.  It then publishes an event like `{"post_id": "xyz", "user_id": "abc"}` to a message queue like Kafka or SQS.
    3.  A pool of workers in the `Fan-out Service` consumes from this queue. For each message, a worker retrieves the follower list for `user_id: "abc"` and performs the timeline injections.
    *   **Benefit:** This decouples the user's initial `POST` request from the expensive fan-out work. The user gets a fast response, and the system handles the distribution in the background. The queue acts as a buffer, smoothing out write spikes.

*   **Timeline Cache Implementation:** A user's timeline is simply a list of `post_id`s. A distributed cache like Redis is a perfect tool.
    *   **Data Structure:** Use a Redis Sorted Set or List. For user `follower_id`, we can have a key like `timeline:follower_id`.
    *   **Injection:** When the `Fan-out Service` processes `post_id: "xyz"`, it adds this ID to the Redis list for each follower. For a sorted set, the score would be the post's timestamp.
    *   **Reading the Feed:** A request to `GET /feed` simply reads the top N elements from the user's Redis timeline list. This is an O(N) operation and extremely fast. Since Redis only stores IDs, the application service then "hydrates" these IDs with the full post content from the `Posts` database/cache.

**5. Scaling and Optimizations: The "Celebrity" Problem**

The pure push model breaks down for users with tens of millions of followers (e.g., a celebrity). A single post would trigger a fan-out of 50 million writes, which is untenable.

*   **The Hybrid Solution:** You must adopt a hybrid approach.
    *   **For most users (<10,000 followers):** Use the standard push/fan-out-on-write model.
    *   **For "celebrity" users:** Do *not* fan out their posts on write.
    *   **When generating a feed for a normal user:**
        1.  Fetch the user's pre-computed timeline from Redis.
        2.  Separately, check if the user follows any celebrities.
        3.  If they do, fetch the latest posts from those celebrities (a pull/fan-out-on-read operation, but only for a small number of accounts).
        4.  Merge the pre-computed feed with the celebrity posts in memory and return the final sorted list.
*   **Trade-off:** This introduces a small amount of complexity and latency on the read path, but it solves the extreme write amplification problem for celebrity posts, making the overall system much more robust. Identifying celebrities can be done by a background job that regularly checks follower counts.

---

### **Design a Follow/Unfollow System**

This system underpins the social feed and presents its own challenges related to data modeling and consistency.

*   **Requirements:** A user can follow another user. A user can unfollow another user. The system must provide a fast way to retrieve a user's `followers` list and `following` list.

*   **API Design:**
    *   `POST /api/v1/users/{user_id}/follow`
    *   `DELETE /api/v1/users/{user_id}/follow`
    *   `GET /api/v1/users/{user_id}/followers`
    *   `GET /api/v1/users/{user_id}/following`

*   **Data Modeling: SQL vs. NoSQL**
    *   **Relational (SQL) Approach:**
        *   A `users` table (`user_id`, `name`, ...).
        *   A `follows` join table (`follower_id`, `followed_id`, `created_at`). Both columns would be foreign keys to the `users` table.
        *   **Queries:** `SELECT followed_id FROM follows WHERE follower_id = ?` (to get following). `SELECT follower_id FROM follows WHERE followed_id = ?` (to get followers).
        *   **Problem:** At massive scale, a single giant join table becomes a bottleneck. Sharding this table correctly is complex, especially when queries need to access the data in two different ways.

    *   **NoSQL (Key-Value/Document) Approach:** This is a much more scalable solution.
        *   Use two "tables" or collections, one for followers and one for following.
        *   `Followers Table:`
            *   Key: `user_id`
            *   Value: A list/set of `follower_ids`.
        *   `Following Table:`
            *   Key: `user_id`
            *   Value: A list/set of `user_ids` they are following.
        *   **Justification:** This denormalizes the data. Retrieving a user's complete follower list is a single key lookup, which is extremely fast and scalable.
        *   **Trade-off:** A single `follow` action now requires two writes (one to the follower's `Following` list, one to the followed user's `Followers` list). This operation must be transactional or idempotent to handle failures. If one write succeeds and the other fails, the graph is in an inconsistent state. This can be managed with retries and cleanup jobs.

*   **Unfollow Operation:** An unfollow is the reverse. It requires two deletes. The atomicity problem is the same. For a system that prioritizes availability and scale over strong consistency (which is appropriate for a social network), accepting eventual consistency here is the correct trade-off. A background process can be used to reconcile any inconsistencies caused by partial failures.