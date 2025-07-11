## **Chapter 8: Back-of-the-Envelope Calculations**

Hand-waving stops here. This chapter is the quantitative foundation upon which every defensible architectural decision is built. The ability to perform rapid, order-of-magnitude estimations is not an academic exercise; it is the engineer's primary tool for sanity-checking a design and identifying bottlenecks before a single line of code is written.

I do not expect you to be a human calculator. The precise numbers are irrelevant. What I am looking for is your *number sense* for systems. Can you reason about whether a problem requires 10 terabytes or 10 petabytes of storage? Do you have an intuitive feel for whether a service will handle 100 queries per second or 100,000? A candidate who cannot ground their design in these reasonable estimates is simply drawing a fantasy. This skill separates architects from illustrators.

---

### **Why These Numbers Matter**

These calculations serve three critical purposes in a system design interview:

1.  **Scoping the Problem:** They translate vague requirements ("a lot of users") into concrete technical constraints ("~15,000 read QPS, ~150 write QPS").
2.  **Justifying Technology Choices:** They provide the evidence needed to justify major architectural decisions. You don't choose to shard a database "because it's scalable"; you choose to shard it because you've calculated that the data set will be multiple terabytes and exceed the capacity of a single machine.
3.  **Proactively Identifying Bottlenecks:** The numbers will scream at you where the system will break. If you calculate that you need 5 TB of storage for your `users` table, you immediately know a single commodity server isn't enough. If you calculate 20 Gbps of egress traffic, you know serving it directly from your origin is financially ruinous, forcing the inclusion of a CDN.

---

### **The Foundational Numbers: Know These Cold**

You must have a mental lookup table for the basics. Not knowing these is like a carpenter not knowing the length of a 2x4.

**The Powers of Two & Ten (for Data)**
*   **Know your bytes:** Kilobyte, Megabyte, Gigabyte, Terabyte, Petabyte.
*   `2^10` = 1,024 ≈ **1 Thousand** (Kilo)
*   `2^20` ≈ **1 Million** (Mega)
*   `2^30` ≈ **1 Billion** (Giga)
*   `2^40` ≈ **1 Trillion** (Tera)
*   `2^50` ≈ **1 Quadrillion** (Peta)

**Latency Numbers (Every Engineer Should Know)**
These numbers dictate where you can and cannot afford to go to get data.
*   L1 cache reference: ~0.5 ns
*   L2 cache reference: ~7 ns (14x L1)
*   Main memory reference: ~100 ns (200x L1)
*   **Round trip within same datacenter:** ~500,000 ns = **0.5 ms**
*   **Send 1MB over 1 Gbps network:** ~10,000,000 ns = **10 ms**
*   **Read from SSD:** ~1 ms
*   **Round trip CA to Netherlands:** ~150,000,000 ns = **150 ms**

**The "Time" Constant**
*   **Seconds in a day:** `24 hours * 60 min/hr * 60 sec/min` ≈ `25 * 3600` = `90,000` (Let's use **86,400** for better precision if needed, but `~10^5` is often fine for quick math).

---

### **The Estimation Framework: A Step-by-Step Guide**

Let's apply these numbers to a simplified "Design a Photo Sharing Service" prompt.

**Step 1: Clarify Assumptions & Write Them Down**
You must start here. State your assumptions about the load so the interviewer can agree or correct you.
*   **Active Users:** "Let's assume we have 500 million total users, and 100 million are active daily (DAU)."
*   **Core Write Action:** "Users upload, on average, 2 photos per day."
*   **Core Read Action:** "On average, each user views 50 photos in their feed per day."
*   **Data Sizes:** "Let's assume the average photo size after compression is 2MB. Metadata per photo (ID, user ID, description, timestamp) is about 1KB."
*   **Growth Rate:** "Let's plan for 5 years of storage."

**Step 2: Calculate Write Load (QPS & Storage)**

*   **Write QPS (Queries Per Second):**
    *   Total photos uploaded per day = `100M DAU * 2 photos/day` = `200M photos/day`
    *   Write QPS = `200M photos / 86,400 seconds/day` ≈ `200,000,000 / 8.6e4` ≈ `2,300 QPS`
    *   This is the peak average QPS for writes. Traffic isn't uniform; it peaks. Assume a peak factor of 2x. **Peak Write QPS ≈ 4,600 QPS.**

*   **Storage (per day):**
    *   Photo data per day = `200M photos/day * 2 MB/photo` = `400 TB/day`
    *   Metadata per day = `200M photos/day * 1 KB/photo` = `200 GB/day`

*   **Total Storage (5 years):**
    *   Total photo data = `400 TB/day * 365 days/year * 5 years` = `730,000 TB` = **730 PB (Petabytes)**
    *   Replication Factor: Assume data is replicated 3x for durability. `730 PB * 3` = **~2.2 Exabytes**.

**Step 3: Calculate Read Load (QPS & Egress)**

*   **Read QPS:**
    *   Total photos viewed per day = `100M DAU * 50 photos/day` = `5 Billion views/day`
    *   Read QPS = `5B views / 86,400 seconds/day` ≈ `5,000,000,000 / 8.6e4` ≈ `58,000 QPS`
    *   Assume a peak factor of 2x. **Peak Read QPS ≈ 116,000 QPS.**
    *   **Crucial Insight:** The read:write ratio is `116,000 / 4,600` ≈ `25:1`. This system is heavily read-dominant.

*   **Egress (Bandwidth):**
    *   Total data served per day = `5B views/day * 2 MB/photo` = `10 PB/day`
    *   Bandwidth = `10 PB/day / 86,400 seconds/day` = `(10 * 10^15 * 8 bits) / 8.6e4 sec` ≈ **~925 Gbps**

---

### **The "So What?": Connecting Calculations to Architecture**

The numbers are meaningless until you interpret them. This is the step where you demonstrate seniority.

*   **On Write QPS (4,600):**
    *   "A peak write QPS of nearly 5,000 is far too high for a single primary relational database. This immediately tells me we cannot use a naive SQL architecture. We need a system that scales writes horizontally. This pushes us toward a NoSQL solution like Cassandra or a sharded RDBMS from day one."

*   **On Read QPS (116,000):**
    *   "The read QPS is enormous. This validates that our design must prioritize the read path. We will need aggressive, multi-layer caching: a CDN for the photos themselves, and a Redis/Memcached layer for the hot feed metadata. The 25:1 read:write ratio further supports using separate read replicas for our metadata store if we go the SQL route."

*   **On Storage (~730 PB without replication):**
    *   "730 Petabytes of photo data is an immense amount. There is no question that this cannot be stored on a traditional filesystem attached to a server. We *must* use a dedicated object storage system like Amazon S3 or Google Cloud Storage. The metadata (~200GB/day) is also substantial, and at `365 TB` over 5 years, the metadata database itself must also be sharded."

*   **On Egress (~925 Gbps):**
    *   "Nearly 1 Terabit per second of egress is a staggering amount of traffic. Serving this from our origin servers would be cost-prohibitive and create a massive network bottleneck. This number alone makes a **Content Delivery Network (CDN) a non-negotiable component** of the architecture. Our cost analysis must account for CDN pricing."

By walking through this process, you have single-handedly used simple arithmetic to justify the need for a distributed NoSQL/sharded database, a multi-layer caching strategy, a dedicated object store, and a CDN. You have moved from a vague prompt to a well-defined set of technical constraints. This is the tangible output of engineering reason, and it is precisely what interviewers are looking for.