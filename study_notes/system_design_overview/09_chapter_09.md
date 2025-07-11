## **Chapter 9: Red Flags & Common Pitfalls**

This is the final filter. An engineer can study every known system design pattern, memorize the CAP theorem, and regurgitate a flawless explanation of a Raft consensus algorithm. Yet, they can still fail this interview, catastrophically. The reason is that this is not a test of rote knowledge. It is a test of judgment.

In my years at Meta, Netflix, and Citadel, I have seen more interview failures rooted in the pitfalls described in this chapter than in any other technical deficiency. These are not obscure "gotchas." They are fundamental errors in approach that signal to me, the interviewer, that while the candidate may know the "what," they lack a deep understanding of the "why." They are hallmarks of an engineer who has not yet borne the scars of maintaining a large-scale system in production. This chapter is your guide to avoiding those unforced errors.

---

### **The Spectrum of Incompetence: Over-engineering vs. Under-engineering**

The most common failure of judgment is a fundamental mismatch between the complexity of the solution and the complexity of the problem. A senior engineer lives in the "Goldilocks zone" of right-sized complexity.

**Pitfall 1: The Over-engineered Solution ("The Résumé-Driven Architect")**

This is the candidate who sees "Design a URL Shortener" and immediately proposes a seven-microservice architecture orchestrated by Kubernetes, communicating via a geo-replicated Kafka cluster with a globally distributed graph database backend.

*   **The Signal:** This tells me the candidate is insecure. They are not solving the problem; they are trying to prove they know every buzzword from the last five years of Hacker News. They are designing for their résumé, not for the user or the business.
*   **The Damage:** This solution would be astronomically expensive to build and maintain. It would be slow, riddled with cross-service latency, and impossible to debug. It demonstrates a complete lack of pragmatism and a failure to appreciate the virtue of simplicity. The most powerful principle in engineering is KISS (Keep It Simple, Stupid), and this candidate has violated it on a monumental scale.
*   **The Interrogation:** My response would be, "This seems incredibly complex for a service that primarily maps one string to another. Can you justify the need for Kafka here when a simple database call would suffice? What specific problem does this complexity solve that a simpler architecture doesn't?" A weak answer here is fatal.

**Pitfall 2: The Under-engineered Solution ("The 2010 Architect")**

This is the other end of the spectrum. The candidate hears "Design a global-scale photo sharing service" and proposes a single monolithic application running on an Apache server connected to a single MySQL database on the same machine.

*   **The Signal:** This tells me the candidate has not been exposed to systems at scale. Their mental model for engineering is stuck in a past era. They have no intuition for the sheer volume of data, traffic, and concurrent requests that modern systems must handle.
*   **The Damage:** This solution is not just suboptimal; it is non-functional. It would collapse the moment it saw a hundredth of its projected traffic. It fails to account for every single non-functional requirement of a large-scale system: availability, scalability, fault tolerance, and performance.
*   **The Interrogation:** I wouldn't even need to ask a question. The back-of-the-envelope calculations from the previous chapter would have already proven this design to be impossible. A candidate proposing this has demonstrated a fundamental lack of understanding before the design even begins.

---

### **The Cardinal Sin: Designing in a Vacuum**

If I am forced to identify the source of all other failures, it is this: designing without first defining and constantly referencing the requirements.

Every single decision—from the choice of database to the caching strategy—must be a direct, justifiable consequence of the functional and non-functional requirements established in the first five minutes.

*   **Red Flag:** The candidate draws a solution and then, when asked *why* they chose a particular technology, they cannot link it back to a specific requirement. "Why NoSQL?" "Because it's scalable." *Why do we need that kind of scalability?* The candidate must be able to respond, "Because we calculated a peak write QPS of 4,600, which would overwhelm a single relational database primary."
*   **Red Flag:** The candidate never once glances back at the requirements written on the board. They become engrossed in a specific technical puzzle (e.g., the perfect hashing algorithm for a URL shortener) while ignoring the more critical system-wide requirements of latency and availability.

Your requirements are your shield and your sword. You use them to defend every decision. Without them, you are just an artist painting boxes on a whiteboard.

---

### **The Hallmarks of the Inexperienced**

These are the specific behaviors that immediately trigger my "fraud detection" senses.

*   **The Hand-Waver:** This candidate glosses over the hardest parts of the problem with vague, magical phrases.
    *   *"And then we just scale the database."* (How? Read replicas? Sharding? What is your sharding key? What are the trade-offs of that key?)
    *   *"We'll put a cache here to make it fast."* (What cache? Redis? Memcached? What is the caching strategy? Cache-aside? Write-through? What is the eviction policy? How do you handle cache invalidation?)
    *   *"We make it asynchronous with a queue."* (Which queue? RabbitMQ? Kafka? What are the delivery guarantees you need? At-least-once? Exactly-once?)
    A senior engineer knows that "the devil is in the details," and these hand-waved statements are precisely where the devils live.

*   **The Black Box Thinker:** This candidate uses components without understanding their fundamental operating characteristics.
    *   They say "load balancer" without being able to articulate the difference between Layer 4 and Layer 7 and why that distinction matters for their application.
    *   They choose a database based on its category (e.g., "document store") without being able to discuss its consistency model or underlying storage engine.
    *   **The Signal:** This indicates surface-level, "tutorial-based" knowledge. They know the name of the tool, but they don't know how it works, when it breaks, or why it was invented.

---

### **The Forgotten Realities**

Finally, a candidate's design must acknowledge that systems operate in the real world, not in a perfect theoretical space.

*   **Ignoring Cost:** A technically brilliant solution that is financially ruinous is a bad solution. A candidate who designs a system that generates petabytes of egress traffic without mentioning a CDN demonstrates a critical blind spot. I need to know that you are thinking about the financial implications of your choices. Mentioning that object storage is cheaper for large blobs or that a CDN is essential for managing bandwidth costs is a strong signal of maturity.
*   **Ignoring Observability:** How do you know your system is working? How do you know when it's breaking? A senior design implicitly includes hooks for monitoring, metrics, and logging. When you draw a service, you should mention what key metrics it should expose (e.g., P99 latency, error rate, queue depth). A design that cannot be observed is a design that is waiting to fail silently and catastrophically.
*   **Ignoring Maintainability:** Who has to get up at 3 AM to fix this? Is the system so complex that debugging it requires a Ph.D. in distributed systems? A pragmatic design values simplicity and ease of operation. This is often the unspoken justification for choosing a managed cloud service (e.g., SQS over self-hosting RabbitMQ). Acknowledging this trade-off—sacrificing some control for a massive gain in operational simplicity—is a hallmark of a seasoned engineer.

Your goal in this interview is not to produce a perfect design. It is to demonstrate that you are a seasoned professional who has internalized these lessons. Avoid these pitfalls, and you will communicate something far more valuable than a correct answer: you will communicate engineering wisdom.