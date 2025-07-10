## Database Replication

Here is the list of database replication methods, ranked from most to least commonly used.

**Master-Slave Replication:** One primary database handles all writes, which are copied to one or more read-only replica databases.
 - **Example 1:** A popular e-commerce website uses read replicas to handle thousands of users browsing product catalogs, which takes the load off the primary database that is processing orders.
 - **Example 2:** A blogging platform maintains a "hot standby" replica. If the master database fails, an administrator can quickly promote the replica to become the new master, minimizing downtime.
 - **Example 3:** A company's business intelligence team runs complex, long-running analytical queries on a replica database to avoid slowing down the main application for customers.

**Consensus-Based Replication (e.g., Raft/Paxos):** Writes are only committed after a majority of servers in a cluster agree, enabling automatic and safe failover without data loss.
 - **Example 1:** A financial trading platform uses a consensus-based system like CockroachDB to ensure that no transactions are ever lost, even if an entire server or data center fails.
 - **Example 2:** Kubernetes uses a distributed key-value store (`etcd`) that relies on the Raft consensus algorithm to manage the entire cluster's state, ensuring all components are always in sync.
 - **Example 3:** A modern cloud-native SaaS application uses a distributed SQL database to provide high availability and strong consistency for user data across multiple geographic regions.

**Multi-Master Replication (Active-Active):** Multiple databases can accept writes simultaneously and replicate their changes to each other, requiring a strategy for conflict resolution.
 - **Example 1:** A global airline booking system allows users in both Europe and Asia to book seats on the same flight, with their writes going to the nearest data center and then synced.
 - **Example 2:** A telecommunications provider manages customer accounts across multiple, fully independent data centers to ensure 100% write uptime, even if one center is disconnected from the network.
 - **Example 3:** A collaborative online tool allows multiple users to edit the same project simultaneously, with changes from each user being accepted by different servers and then merged.

**Semi-Synchronous Replication:** A mode for Master-Slave where the master waits for at least one slave to confirm it has received a change before confirming the transaction to the client.
 - **Example 1:** An online payment gateway ensures a transaction record is safely stored on a second machine before telling the customer their payment was successful.
 - **Example 2:** A user registration system prevents a new user's account from being lost if the master server crashes a millisecond after they click "sign up."
 - **Example 3:** An inventory management system for a warehouse, where confirming a customer's order must wait until the stock level update is guaranteed to be replicated to a backup server.

**Snapshot Replication:** A point-in-time copy of a database is taken and moved to another server, typically on a recurring schedule.
 - **Example 1:** A retail company copies its entire sales database every night to a data warehouse so business analysts can build reports without impacting production.
 - **Example 2:** A development team creates a fresh copy of the production database every Monday for their staging environment to test new features on realistic data.
 - **Example 3:** An organization archives its quarterly financial records for compliance by taking a snapshot and storing it in secure, long-term storage.

**Logical Replication:** A flexible method that replicates data based on its content (publication/subscription model), allowing for selective replication of specific tables or rows.
 - **Example 1:** A company consolidates customer data from several smaller databases (each in a different store location) into a single, central analytics database.
 - **Example 2:** Replicating only the `users` and `products` tables from a master database to a public-facing microservice, while keeping the sensitive `payments` table private.
 - **Example 3:** Performing a zero-downtime major version upgrade of a PostgreSQL database by replicating from the old version server to the new one until they are in sync.

**Hierarchical (Tree) Replication:** A primary master replicates to a few intermediate servers, which in turn replicate to many leaf-node servers, forming a distribution tree.
 - **Example 1:** A major news organization distributes breaking news articles to hundreds of servers around the world to handle massive, sudden traffic spikes from readers.
 - **Example 2:** A large social media platform fans out user posts to a vast fleet of regional read replicas to ensure fast timeline loading for all users globally.
 - **Example 3:** A Content Delivery Network (CDN) uses a tree structure to efficiently propagate configuration changes from a central point to all of its thousands of edge nodes.

**Merge Replication:** Designed for disconnected environments where databases can be modified independently and later synchronized by merging changes.
 - **Example 1:** A field sales team uses a mobile app on tablets to place customer orders while offline; the orders are synced back to the central server when they regain internet access.
 - **Example 2:** A research vessel at sea collects scientific data on a local database, which is then merged with the main university database upon returning to port.
 - **Example 3:** A company with several remote branch offices that have unreliable network connections allows them to work locally and sync data with headquarters overnight.

**Delayed Replication:** A slave database is intentionally configured to lag behind the master by a set amount of time (e.g., 6 hours).
 - **Example 1:** A database administrator halts a 6-hour delayed replica to recover a critical `customers` table that was accidentally deleted from the master 30 minutes ago.
 - **Example 2:** A company protects itself from a buggy software deployment that starts corrupting data by stopping the delayed slave before the corrupting commands are applied there.
 - **Example 3:** Using a 24-hour delayed slave to investigate a major data inconsistency issue by examining the exact state of the database before the problem began.

**Circular Replication:** A fragile setup where databases are arranged in a ring, with each one replicating to the next in the chain (A→B→C→A).
 - **Example 1:** A small, three-office company creates a low-cost but brittle setup where each office can make updates that eventually propagate to the others.
 - **Example 2:** A legacy system built over a decade ago to share workload between a few servers, before more robust multi-master solutions were widely available.
 - **Example 3:** A lab or test environment set up purely to demonstrate replication principles, but not intended for production use due to its unreliability.