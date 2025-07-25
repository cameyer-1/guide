### 1) Understanding and Visualization

The problem requires us to find the minimum number of boats needed to transport a group of people, where each boat has a weight `limit` and can hold at most two individuals.

Let's use the example `people = [3, 2, 2, 1]` with `limit = 3`.

We have four people with distinct weights. Our task is to pair them up or send them individually in boats such that we use the fewest boats possible.

*   **People to save:** A group of four individuals with weights `[1, 2, 2, 3]`.
*   **Boat capacity (`limit`):** 3
*   **Goal:** Group these people into boats, using the minimum number of boats possible.

Let's consider our options:
- We can try to pair the heaviest person (weight 3) with someone. The only available people have weights 1, 2, and 2.
    - `3 + 1 = 4` (exceeds limit)
    - `3 + 2 = 5` (exceeds limit)
- Since the heaviest person cannot be paired with anyone, they must take a boat alone.
    - **Boat 1:** `(3)`
- Now we have three people remaining with weights `[1, 2, 2]`. Let's take the next heaviest person (weight 2).
    - Can they be paired with the other person of weight 2? `2 + 2 = 4` (exceeds limit).
    - Can they be paired with the person of weight 1? `2 + 1 = 3` (within limit). This works!
    - **Boat 2:** `(2, 1)`
- Finally, one person with weight 2 remains. They must take a boat by themselves.
    - **Boat 3:** `(2)`

The total number of boats required is 3. This matches the example's output and suggests that prioritizing the heaviest person is a good strategy.

### 2) Brute Force Approach

A brute-force solution would explore all possible ways of grouping people into boats.

1.  We could try every possible pairing of people whose combined weight is under the limit.
2.  For each valid pairing, we would remove those two people from the pool and recursively solve the problem for the remaining people.
3.  We would also need to consider the case where a person takes a boat alone.
4.  Finally, we would take the minimum boat count across all these possibilities.

This approach leads to a combinatorial explosion. The number of partitions of a set is very large, and trying all of them would be computationally infeasible. For example, we would have to check pairs, then pairs of pairs, and so on. A simpler, but still inefficient, O(N²) algorithm would be to iterate through the list, and for each person, scan the rest of the list for a suitable partner. This is too slow given the constraint `N <= 5 * 10^4`.

### 3) Optimization

The key insight is that the fate of the heaviest person is the most constrained. If the heaviest person can share a boat, it's always optimal to pair them with the lightest person. Why? Because pairing them with anyone else would leave the lightest person for a future pairing. That lightest person occupies the least "capacity" and is the easiest to pair. Saving them for later doesn't help. If the heaviest person *cannot* be paired with the lightest person, they cannot be paired with anyone else (since everyone else is heavier).

This leads to a greedy algorithm using two pointers.

**Greedy Strategy:**
1.  **Sort:** First, sort the `people` array in ascending order. This places the lightest people at the beginning and the heaviest at the end.
2.  **Two Pointers:** Initialize a `left` pointer at the start of the array (lightest person) and a `right` pointer at the end (heaviest person).
3.  **Pairing Logic:**
    - Examine the people at the `left` and `right` pointers.
    - If `people[left] + people[right] <= limit`, they can share a boat. We count one boat for this pair and move both pointers inward (`left++`, `right--`).
    - If `people[left] + people[right] > limit`, the heaviest person (`people[right]`) is too heavy to be paired with even the lightest available person. Therefore, they must take a boat alone. We count one boat for them and move the `right` pointer inward (`right--`), leaving the `left` person to be considered in the next step.
4.  **Termination:** Continue this process until the pointers cross (`left > right`), which means everyone has been assigned a boat.

**Complexity Analysis:**
-   **Time Complexity:** O(N log N) for the initial sort. The two-pointer scan is O(N). The dominant factor is sorting.
-   **Space Complexity:** O(log N) to O(N), depending on the implementation of the sort algorithm.

This is a very efficient approach compared to the brute-force O(N²).

### 4) Walk-through

Let's apply the optimized algorithm to our example: `people = [3, 2, 2, 1]`, `limit = 3`.

**Step 1: Sort the array**
The `people` array becomes `[1, 2, 2, 3]`.

**Step 2: Initialize pointers and counter**

*   Sorted `people`: `[1, 2, 2, 3]`
*   `left` pointer: at index 0 (value `1`)
*   `right` pointer: at index 3 (value `3`)
*   `boats`: 0

---
**Iteration 1:**

*   **Pointers:** `left = 0`, `right = 3`.
*   **People considered:** `people[left]` (1) and `people[right]` (3).
*   **Check:** `1 + 3 = 4`. This is greater than `limit` (3).
*   **Action:** The heaviest person (3) cannot be paired. They must take a boat alone. We use one boat for this person. The person at `right` is now accounted for.
*   **Resulting State:**
    *   `boats` is now 1.
    *   `right` pointer moves to index 2 (value `2`).
    *   `left` pointer remains at index 0 (value `1`).

---
**Iteration 2:**

*   **Pointers:** `left = 0`, `right = 2`.
*   **People considered:** `people[left]` (1) and `people[right]` (2).
*   **Check:** `1 + 2 = 3`. This is less than or equal to `limit` (3).
*   **Action:** The two can be paired. We use one boat for them. Both people are now accounted for.
*   **Resulting State:**
    *   `boats` is now 2.
    *   `right` pointer moves to index 1 (value `2`).
    *   `left` pointer moves to index 1 (value `2`).

---
**Iteration 3:**

*   **Pointers:** `left = 1`, `right = 1`. The pointers meet.
*   **People considered:** There is only one person left to consider, `people[1]` (2).
*   **Check:** The loop condition `left <= right` is true. The person must take a boat. In our algorithm's logic, we would use one boat and check if they can be paired (which they can't, since `left` and `right` are the same). The person at `right` is assigned a boat.
*   **Action:** We use one boat for this last person.
*   **Resulting State:**
    *   `boats` is now 3.
    *   `right` pointer moves to index 0.
    *   `left` pointer remains at index 1.

---
**Termination:**

*   Now `left = 1` and `right = 0`. The condition `left <= right` is false, so the loop terminates.
*   The final result is `boats = 3`.

### 5) Implementation

```python
from typing import List

def numRescueBoats(people: List[int], limit: int) -> int:
    """
    Calculates the minimum number of boats to save all people using a greedy 
    two-pointer approach.
    """
    
    # Step 1: Sort the array. This is crucial for the greedy strategy, as it 
    # allows us to consider the lightest and heaviest people at the same time.
    people.sort()
    
    # Step 2: Initialize two pointers and the boat counter.
    # 'left' starts at the beginning (lightest person).
    # 'right' starts at the end (heaviest person).
    left = 0
    right = len(people) - 1
    boats = 0
    
    # Step 3: Iterate until all people are on boats.
    # The loop continues as long as the left pointer is to the left of or at the
    # same position as the right pointer. This ensures every person is considered.
    while left <= right:
        # Each iteration of the loop represents one boat being dispatched. This boat
        # will always carry the heaviest available person (at `right`).
        boats += 1
        
        # We greedily check if the lightest available person (at `left`) can
        # also fit in the same boat without exceeding the weight limit.
        if people[left] + people[right] <= limit:
            # If they fit, we can save the lightest person on this boat as well.
            # We move the 'left' pointer forward, as this person is now accounted for.
            left += 1
            
        # The heaviest person (at 'right') is always placed in the current boat,
        # regardless of whether they are paired or alone. So, we move the 'right'
        # pointer inward to consider the next-heaviest person in the next iteration.
        right -= 1
        
    # Step 4: Return the total count of boats used.
    return boats

```

### 6) Follow-ups

**1. Why does this greedy strategy guarantee an optimal solution?**

The proof relies on the decisions made for the heaviest person at each step. Let the heaviest person be `P_h` and the lightest be `P_l`.

- **Case 1: `P_h` and `P_l` can be paired (`P_h + P_l <= limit`).**
  Our algorithm pairs them. An alternative would be to send `P_h` alone or pair `P_h` with someone else, `P_x`. Sending `P_h` alone is less efficient than pairing them if possible. Pairing `P_h` with `P_x` (where `P_x` is heavier than `P_l`) would leave the lightest person `P_l` for a later pairing, which is no better (and potentially worse) than pairing `P_l` now. So, pairing `P_h` and `P_l` is the optimal move.

- **Case 2: `P_h` and `P_l` cannot be paired (`P_h + P_l > limit`).**
  Since `P_l` is the lightest person available, `P_h` cannot be paired with *anyone* else (as all others are heavier than `P_l`). Therefore, `P_h` must take a boat alone. This move is forced upon us, and any optimal solution must do the same.

Since every step involves making a choice that is locally optimal and demonstrably the best possible move, the overall solution is globally optimal.

**2. What if each boat could carry at most `k` people (where `k > 2`)?**

The problem becomes significantly harder. The simple two-pointer greedy approach is no longer sufficient because the decision space is much larger. With `k` slots, we might need to pair the heaviest person with one or more of the lightest people. This is a variation of the **Bin Packing Problem**, which is NP-hard. Finding a guaranteed optimal solution would require more complex algorithms, such as dynamic programming with bitmasking or backtracking, which would only be feasible for very small `N`.

**3. What is the time and space complexity? Can we do better?**

- **Time Complexity:** `O(N log N)`, dominated by `people.sort()`.
- **Space Complexity:** `O(log N)` to `O(N)`, the auxiliary space required by the sorting algorithm.

- **Can we do better?** Yes, by avoiding a comparison-based sort. Since the weights are integers within a known range (`1 <= people[i] <= limit`), we can use a non-comparison sort like **Counting Sort**.

    1.  **Create a frequency map (or an array) `counts`** of size `limit + 1`, where `counts[w]` stores the number of people with weight `w`. This takes `O(N + limit)` time.
    2.  **Use two pointers, `l` and `r`**, to scan this `counts` array from `l=1` to `r=limit`.
    3.  **Adapt the logic:** While `l <= r`, we try to pair people of weight `l` with people of weight `r`. We decrement the counts in the `counts` array instead of moving pointers in the `people` array.
    
    This modified approach has a time complexity of **O(N + L)** and space complexity of **O(L)**, where `L` is the `limit`. Given the problem constraints (`N` up to 50k, `L` up to 30k), this is asymptotically faster than the `O(N log N)` solution.