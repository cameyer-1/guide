### **Chapter 1: The Art of Scoping**

The system design interview is an exercise in applied engineering philosophy. It is not a trivia contest about the latest database technologies, nor is it a race to fill a whiteboard with boxes and arrows. It is a structured exploration of your ability to navigate ambiguity, justify trade-offs, and build a mental model of a complex system from the ground up.

The most common—and most catastrophic—mistake an engineer can make is to begin this exploration by choosing a tool. The moment you say "We'll use Kubernetes" or "I'd pick Cassandra for this" before you have defined what *this* is, you have failed the primary test. You have demonstrated a fatal fixation on the *how* before you have established any agreement on the *what*.

This chapter is about mastering the first, and most critical, phase of the interview: taking a vague, one-sentence prompt and forging it into a concrete engineering contract.

---

### **1.1 Functional Requirements: From Ambiguity to a Concrete Feature List (V1, V2...)**

The interviewer will give you a prompt deliberately designed to be ambiguous. "Design Twitter." "Design a ride-sharing app." "Design Netflix." This is not an accident; it is the first test. Your interviewer is assessing:

1.  Your ability to manage ambiguity without panic.
2.  Your product sense—can you distill a massive product down to its essential essence?
3.  Your ability to take control and drive the conversation with a structured process.

Your first move must always be to define the Functional Requirements. These requirements dictate what the system must *do*. They are the verbs of your system, the actions your users can take.

The strategy here is to build a "V1"—a Minimum Viable Product—and explicitly park everything else for a "V2" or "V-Next." This demonstrates pragmatism and a keen awareness of the constraints of the interview format.

#### **The Scoping Framework**

Follow this process methodically. Do not skip a step.

1.  **Identify Core Actors:** Who are the primary users of this system? Write them down. For a ride-sharing app, the actors are "Rider" and "Driver." For an e-commerce site, they are "Buyer" and "Seller."
2.  **Map Core User Journeys:** For each actor, what is the single most critical journey they must complete? Think in terms of a simple narrative.
    *   *Rider Journey:* I need to open the app, get a ride from where I am to where I'm going, and pay for it.
    *   *Driver Journey:* I need to go online, be matched with a rider, navigate to them, complete the ride, and get paid.
3.  **Distill into Core Features:** Translate these narrative journeys into a clear, numbered list of features. These are your V1 Functional Requirements. Be imperative and unambiguous. Use language like "The system *must* allow a user to..."
4.  **Create an Explicit "Parking Lot":** Equally important is defining what you are *not* building today. This prevents scope creep and shows the interviewer you are making conscious decisions to simplify the problem.

#### **Illustrative Example: "Design a Ride-Sharing App"**

Let's apply the framework to this classic prompt.

**V1 Functional Requirements:**

1.  **User Authentication:** A Rider and a Driver must be able to sign up and log into the system.
2.  **Location Reporting:** An active Driver must be able to broadcast their current location and availability.
3.  **Ride Discovery & Request:** A Rider must be able to see nearby available Drivers and request a ride from Point A to Point B.
4.  **Driver Matching:** The system must match an open ride request to a single, suitable Driver.
5.  **Real-Time Ride Tracking:** Both Rider and Driver must be able to see each other's live location on a map from acceptance to pickup.
6.  **Ride State Management:** Both parties must be able to progress through the states of a ride (e.g., `Accepted`, `En Route to Rider`, `Ride in Progress`, `Completed`).
7.  **Payment Processing:** The system must handle payment automatically upon ride completion.
8.  **Ratings & Feedback:** A Rider and a Driver must be able to rate each other after a ride.

This list is your engineering contract for the next 45 minutes. It is specific, bounded, and complex enough to be interesting.

**The "Parking Lot" (Out of Scope for V1):**

To demonstrate focus, you must explicitly state what you are deferring.

1.  **Scheduled Rides:** V1 is on-demand only.
2.  **Shared Rides / Pooling:** V1 is for private rides only.
3.  **Multiple Service Tiers:** No different vehicle types (e.g., XL, Lux). All rides are standard.
4.  **In-App Chat:** Rider and Driver cannot communicate within the app.
5.  **Dynamic/Surge Pricing:** All pricing is based on a simple distance/time model. The logic for surge detection is a V2 problem.
6.  **Complex Payout Systems:** Driver payments are handled in a simplified manner; no instant payouts or detailed financial dashboards.

By the end of this five-to-ten-minute process, you have transformed an amorphous cloud of a problem into a solid foundation. You have established yourself as a methodical engineer who builds from first principles. Every subsequent technical decision—your choice of database, your API design, your caching strategy—can and will be justified directly against this clear, mutually agreed-upon list of requirements.

### **1.2 Non-Functional Requirements: The “ilities” That Shape the Architecture**

If Functional Requirements are the *what*, Non-Functional Requirements (NFRs) are the *how well*. They are the constraints, the performance targets, and the quality attributes that dictate the very shape of the system. Two systems can have identical functional requirements but be built in wildly different ways because of their NFRs.

Consider two cars. Both have the same functional requirements: an engine, four wheels, a steering wheel, and seats. But one is a budget-friendly family sedan, and the other is a Formula 1 race car. They are not the same machine. Their differences are defined by their NFRs: speed (latency), reliability (availability), fuel efficiency (operational cost), and safety rating (durability).

In a system design interview, defining the NFRs is your opportunity to demonstrate senior-level thinking. It is where you move beyond simple feature lists and begin to grapple with the engineering trade-offs that lie at the heart of the problem. Your interviewer is looking to see if you can translate vague business needs like "the app should be fast and reliable" into quantifiable engineering targets.

#### **Quantify Everything**

The most significant difference between a junior and a senior engineer's approach to NFRs is the use of numbers. A junior engineer says, "We need high availability." A senior engineer says, "We are targeting 99.99% availability, which gives us a budget of 52 minutes of downtime per year." This quantification is non-negotiable. It provides a concrete goalpost against which you can measure every architectural decision.

Here are the core NFRs to define for almost any system:

#### **Scalability**
*   **What it is:** The system’s ability to handle a growing amount of load, whether that load is users, data, or transaction volume.
*   **How to quantify it:** Use the estimates you derived earlier. State the target number of users (e.g., 10 Million Daily Active Users) and the resulting query load (e.g., "This translates to a peak write load of 50k QPS and a peak read load of 500k QPS"). Differentiate between read and write scaling needs.
*   **Architectural Impact:** This is the primary driver for horizontal scalability. It forces you to design stateless services that can be easily cloned behind a load balancer. It heavily influences your database choice, pushing you away from monolithic, single-server databases towards systems designed to be distributed and sharded from the outset.

#### **Latency**
*   **What it is:** The time it takes for the system to respond to a user's action. This is often called response time and is a direct measure of the system's "speed."
*   **How to quantify it:** Never use averages; they hide outliers that ruin the user experience. Use percentiles: P95, P99, or even P99.9. For example: "For our ride-sharing app, the P99 latency for a driver's location update to reach the rider must be under 500ms. The P95 latency for fetching a user's ride history should be under 300ms."
*   **Architectural Impact:** Aggressive latency targets demand aggressive optimization. This requirement dictates the use of Content Delivery Networks (CDNs) to serve static assets, introduces multiple layers of caching (in-memory, distributed), forces decisions on data center geography (placing servers closer to users), and can influence protocol choices (e.g., persistent WebSocket connections vs. stateless HTTP requests).

#### **Availability**
*   **What it is:** The percentage of time the system is operational and able to serve requests. This is the measure of the system's reliability.
*   **How to quantify it:** Use "the nines."
    *   **99%** ("two nines") = ~3.65 days of downtime/year. (Unacceptable for most services)
    *   **99.9%** ("three nines") = ~8.77 hours of downtime/year. (A common target for internal services)
    *   **99.99%** ("four nines") = ~52.6 minutes of downtime/year. (A strong target for a V1 user-facing service)
    *   **99.999%** ("five nines") = ~5.26 minutes of downtime/year. (The gold standard, extremely expensive to achieve)
*   **Architectural Impact:** Availability is the reason we build distributed systems. A 99.99% target immediately means there can be no single point of failure (SPOF). Every component—from load balancers to application servers to databases—must have redundancy, typically across multiple physical locations (Availability Zones or even Regions). It mandates health checks, automated failover, and robust deployment strategies.

#### **Consistency**
*   **What it is:** A guarantee about the state of data as seen by different clients at the same time. This is the "C" in the CAP theorem.
*   **How to quantify it:** This is typically described qualitatively. The two primary models are:
    *   **Strong Consistency:** All reads are guaranteed to see the result of the most recently completed write. This is what users intuitively expect.
    *   **Eventual Consistency:** After a write, there is a period of time during which reads might return stale data. The system guarantees that, given enough time with no new writes, all replicas will eventually converge to the same value.
*   **Architectural Impact:** This is a fundamental trade-off against availability and latency. For a ride-sharing app, you need *strong consistency* for the state of the ride itself (you can't have a driver think the ride is `Completed` while the rider thinks it's `In Progress`). However, for the driver's icon moving on the map, *eventual consistency* is perfectly acceptable. Recognizing this allows you to build a more performant and resilient system by relaxing constraints where possible.

#### **Durability**
*   **What it is:** The guarantee that once the system acknowledges a write, the data will not be lost, even in the face of server crashes, network partitions, or catastrophic failures.
*   **How to quantify it:** Also expressed in "nines," but referring to the probability of data loss. Cloud storage providers like Amazon S3 famously offer "11 nines" of durability.
*   **Architectural Impact:** Durability forces you to think about persistence strategies. It drives the need for database replication (writing data to multiple servers), persistent Write-Ahead Logs (WALs), and robust backup and restore plans. For critical user data, you can't just store it on one server's disk; you must ensure it is replicated across multiple failure domains.

By defining these five NFRs with specific, quantifiable targets, you create a scorecard. Now, when you propose to use a particular technology or architectural pattern, the interviewer will expect you to justify it based on how well it helps you meet these targets. You have successfully framed the rest of the conversation around concrete engineering goals.

### **1.3 Defining What's Explicitly Out of Scope**

In the art of sculpture, the masterpiece is revealed not by adding clay, but by chipping away the marble that isn't part of the statue. Similarly, in a system design interview, defining a world-class architecture is as much about what you choose *not* to build as what you choose to build.

Explicitly defining features that are "Out of Scope" is one of the most potent signals of seniority you can send. It demonstrates pragmatism, focus, and a keen understanding of the interview's constraints. An engineer who tries to design every feature of a product in 45 minutes is demonstrating ambition but also a critical lack of real-world project management sense.

The purpose of this exercise is to create a "Parking Lot" or "V2 List." This is a mutually agreed-upon list of features that are acknowledged as important but are deliberately deferred. This action serves several crucial purposes:

*   **It Manages Time:** It is the single most effective tool for keeping the interview on track.
*   **It Controls the Narrative:** It allows you to define the boundaries of the problem, preventing the interviewer from leading you down a complex rabbit hole you haven't prepared for.
*   **It Reduces Ambiguity:** It creates a firm contract. By stating what's out, you are reinforcing what's in, ensuring both you and the interviewer are solving the same problem.
*   **It Showcases Product Acumen:** It shows you can think like a product manager—you understand the concept of a Minimum Viable Product (MVP) and the necessity of phased rollouts.

#### **How to Identify and Defer Features**

Your goal is to identify features that, while valuable, represent a significant and distinct engineering sub-problem. Look for features that would require their own dedicated design session.

1.  **Listen for High-Complexity Keywords:** When you brainstorm initial features, be on the lookout for things that imply whole new domains of computer science or infrastructure.
    *   "Real-time..." → often implies a need for a dedicated data streaming pipeline (e.g., Kafka, Flink).
    *   "Machine Learning..." → implies a need for ML model training, feature stores, and inference engines.
    *   "Social Graph..." → implies a need for a graph database and complex query patterns.
    *   "Chat/Video Call..." → implies a need for real-time messaging infrastructure (WebSockets) or WebRTC servers.

2.  **Acknowledge, Praise, and Defer:** Don't just ignore these features. The technique is to validate their importance and then politely postpone them. The phrasing is key:
    *   *"Surge pricing is a critical revenue driver and a fascinating data science problem. For the purposes of our V1 today, let's stick to a simpler pricing model and park 'surge pricing' in our V2 list. This will allow us to focus on the core ride-hailing mechanics."*
    *   *"An in-app chat is essential for good user experience. However, that requires a full real-time messaging subsystem. Let's place that on the V2 list and assume for now that communication can happen out-of-band."*

#### **Illustrative Example: "Ride-Sharing App" Parking Lot**

Let's revisit our ride-sharing app and justify the items in its "Parking Lot." Notice how each deferred feature represents a new axis of complexity.

*   **Out of Scope: Surge Pricing**
    *   **Justification:** This isn't just a simple `price * 1.5` calculation. A proper implementation requires a separate, complex subsystem to:
        1.  Ingest real-time location data from all drivers and active riders.
        2.  Divide the city into geographical cells (e.g., using S2 or Geohash).
        3.  Calculate the supply-demand ratio in each cell in near real-time.
        4.  Store and analyze historical demand patterns.
        5.  Communicate this data back to users without creating a thundering herd.
    *   This is a classic stream-processing and data-analytics problem, distinct from the core transactional ride state machine.

*   **Out of Scope: Shared Rides (Pooling)**
    *   **Justification:** This fundamentally changes the complexity of two core components:
        1.  **Matching Algorithm:** We move from matching one rider to one driver (a relatively simple search problem) to a multi-variable optimization problem that resembles the Traveling Salesman Problem. The algorithm must now consider multi-stop routes, estimated time of arrival for subsequent passengers, and route deviation.
        2.  **Ride State Machine:** The system must now manage a ride with multiple legs and multiple distinct passenger states (`rider1_picked_up`, `en_route_to_rider2`, etc.).

By deliberately placing these items on the back burner, you are not showing weakness. You are demonstrating the focused, methodical discipline of a senior engineer who knows how to de-risk a project by tackling its core functionality first. You have cleanly defined the boundaries of the statue and are now ready to begin sculpting.