### 1) Understanding and Visualization

The problem asks us to sort an array containing only three distinct values: 0, 1, and 2. We should do this "in-place," meaning we modify the given array directly without creating a new one. The final sorted array should have all the 0s first, followed by all the 1s, and finally all the 2s.

Let's take the example `nums = [2, 0, 2, 1, 1, 0]`.

*   **Input:** An array of numbers representing colors (0: red, 1: white, 2: blue).
    ```
    Index:  0  1  2  3  4  5
    Value: [2, 0, 2, 1, 1, 0]
    ```
*   **Goal:** Re-arrange the elements within this same array so they are in ascending order.
    ```
    Index:  0  1  2  3  4  5
    Value: [0, 0, 1, 1, 2, 2]
    ```

The core constraints are:
1.  **In-place sorting:** We must not use significant extra memory (i.e., O(1) extra space).
2.  **No library sort:** We cannot simply call `nums.sort()`.

### 2) Brute Force Approach

The simplest way to solve this is to count the occurrences of each color and then overwrite the array with the correct number of 0s, 1s, and 2s. This is a variation of Counting Sort.

This approach involves two passes over the data:

*   **Pass 1: Count Frequencies**
    1.  Initialize three counters: `count0 = 0`, `count1 = 0`, `count2 = 0`.
    2.  Iterate through the `nums` array from beginning to end.
    3.  If we see a 0, increment `count0`. If we see a 1, increment `count1`. If we see a 2, increment `count2`.

    For our example `[2, 0, 2, 1, 1, 0]`, after this pass we would have:
    *   `count0 = 2`
    *   `count1 = 2`
    *   `count2 = 2`

*   **Pass 2: Overwrite the Array**
    1.  Now, iterate through the `nums` array again, this time filling it up based on our counts.
    2.  Fill the first `count0` elements with `0`.
    3.  Fill the next `count1` elements with `1`.
    4.  Fill the final `count2` elements with `2`.

    For our example:
    *   `nums[0]` and `nums[1]` become `0`.
    *   `nums[2]` and `nums[3]` become `1`.
    *   `nums[4]` and `nums[5]` become `2`.

The final array is `[0, 0, 1, 1, 2, 2]`, which is the correct solution.

*   **Time Complexity:** O(N) for the first pass + O(N) for the second pass = **O(N)**.
*   **Space Complexity:** O(1), as we only use a few extra variables to store the counts.

This solution works and is efficient, but it requires two passes. The follow-up question specifically asks for a one-pass algorithm.

### 3) Optimization

To achieve a single-pass solution with constant space, we can use a partitioning strategy. This problem is a classic example of the **Dutch National Flag problem**, proposed by Edsger W. Dijkstra.

The idea is to partition the array into three sections during a single iteration:
1.  A section for 0s at the beginning of the array.
2.  A section for 2s at the end of the array.
3.  A section for 1s that will naturally form in the middle.

We can manage these sections using three pointers:
*   `left`: Marks the boundary of the 0s section. Everything to the left of `left` is a `0`.
*   `right`: Marks the boundary of the 2s section. Everything to the right of `right` is a `2`.
*   `current`: The pointer that iterates through the array, processing one element at a time.

The algorithm proceeds as follows:
*   Initialize `left = 0`, `current = 0`, and `right = n - 1`.
*   Iterate with the `current` pointer as long as `current <= right`.
    *   **If `nums[current]` is 0:** It belongs in the `left` section. We swap `nums[current]` with `nums[left]`. Since the element we just moved to the `current` position came from the `left` region (which has already been processed), we can safely increment both `left` and `current`.
    *   **If `nums[current]` is 2:** It belongs in the `right` section. We swap `nums[current]` with `nums[right]`. Then, we decrement `right`. **Crucially, we do not increment `current`** because the new element at `nums[current]` came from the unprocessed `right` region and we must re-evaluate it in the next iteration.
    *   **If `nums[current]` is 1:** It is in the correct eventual place (between the 0s and 2s). We don't need to move it, so we just increment `current` to check the next element.

The loop terminates when `current` surpasses `right`, at which point the entire array has been partitioned correctly.

### 4) Walk-through

Let's walk through the optimized one-pass solution with our example `nums = [2, 0, 2, 1, 1, 0]`.

*   **Initial State:**
    *   `nums = [2, 0, 2, 1, 1, 0]`
    *   `left = 0`
    *   `current = 0`
    *   `right = 5`

    ```
     left, current                    right
       ↓                              ↓
      [2,   0,   2,   1,   1,   0]
    ```

| `current` | `nums[current]` | Condition Met     | Action                                         | `nums` after Action         | Pointer Updates        |
| :-------- | :-------------- | :---------------- | :--------------------------------------------- | :-------------------------- | :--------------------- |
| 0         | 2               | `nums[current]==2` | Swap `nums[0]` with `nums[5]`.                 | `[0, 0, 2, 1, 1, 2]`        | `right--` (to 4)       |
| 0         | 0               | `nums[current]==0` | Swap `nums[0]` with `nums[0]` (no change).      | `[0, 0, 2, 1, 1, 2]`        | `left++`, `current++`  |
| 1         | 0               | `nums[current]==0` | Swap `nums[1]` with `nums[1]` (no change).      | `[0, 0, 2, 1, 1, 2]`        | `left++`, `current++`  |
| 2         | 2               | `nums[current]==2` | Swap `nums[2]` with `nums[4]`.                 | `[0, 0, 1, 1, 2, 2]`        | `right--` (to 3)       |
| 2         | 1               | `nums[current]==1` | Do nothing, element is in place.               | `[0, 0, 1, 1, 2, 2]`        | `current++`            |
| 3         | 1               | `nums[current]==1` | Do nothing, element is in place.               | `[0, 0, 1, 1, 2, 2]`        | `current++`            |
| 4         | -               | Loop terminates (`current > right`) | -                               | `[0, 0, 1, 1, 2, 2]` (Final) | -                      |

After the final step, the loop condition `current <= right` (i.e., `4 <= 3`) is false, so the process stops. The array is now successfully sorted in one pass.

### 5) Implementation

Here is the Python implementation of the one-pass Dutch National Flag algorithm.

```python
from typing import List

class Solution:
    def sortColors(self, nums: List[int]) -> None:
        """
        Sorts an array of 0s, 1s, and 2s in-place using the Dutch National Flag algorithm.
        This is a one-pass algorithm with constant extra space.
        """
        # Ensure the array is not empty
        if not nums:
            return

        # Initialize pointers.
        # `left` points to the position where the next 0 should go.
        # `right` points to the position where the next 2 should go.
        # `current` is the pointer iterating through the array.
        left, current, right = 0, 0, len(nums) - 1

        # The loop continues as long as `current` has not surpassed `right`.
        # The region between `current` and `right` (inclusive) is the unprocessed part of the array.
        while current <= right:
            
            # Case 1: The element is a 0.
            if nums[current] == 0:
                # A 0 belongs to the left section. Swap it with the element at the `left` pointer.
                nums[left], nums[current] = nums[current], nums[left]
                
                # Increment `left` because we have placed a 0 correctly.
                left += 1
                
                # Increment `current` because the element we swapped from `left` has already been
                # processed (it can't be a 2), so we can move on.
                current += 1

            # Case 2: The element is a 2.
            elif nums[current] == 2:
                # A 2 belongs to the right section. Swap it with the element at the `right` pointer.
                nums[right], nums[current] = nums[current], nums[right]
                
                # Decrement `right` because we have placed a 2 correctly at the end.
                right -= 1
                
                # IMPORTANT: Do NOT increment `current`. The new element at `nums[current]`
                # came from the `right` and has not been processed yet. We must re-examine it
                # in the next iteration of the loop.
                
            # Case 3: The element is a 1.
            else: # nums[current] == 1
                # A 1 is in its correct place relative to 0s and 2s.
                # We simply move to the next element.
                current += 1
```

### 6) Followups

#### Follow-up 1: "What if there were *k* colors (0, 1, 2, ..., k-1) instead of just 3? How would your algorithm change?"

The Dutch National Flag algorithm is specifically optimized for three partitions. Generalizing it to *k* colors while maintaining a single pass and constant space is not straightforward. The most practical approach for `k` colors would be:

**Counting Sort (Two-Pass):**
This is the most common and efficient solution for this generalization, especially if `k` is reasonably small.
1.  **First Pass:** Create a frequency map or an array of size `k` to count the occurrences of each color (from 0 to `k-1`). Time: O(N), Space: O(k).
2.  **Second Pass:** Overwrite the original array using the counts from the frequency map. Time: O(N).

Overall complexity would be O(N + k) time and O(k) space. For a fixed `k`, this is O(N) time and O(1) space, which is highly efficient.

#### Follow-up 2: "Can you explain the loop invariant for your one-pass solution?"

A loop invariant is a condition that is true before the first iteration of a loop and remains true before and after every subsequent iteration. For our three-pointer algorithm, the invariant is maintained throughout the `while current <= right` loop:

1.  `nums[0...left-1]` contains only 0s.
2.  `nums[left...current-1]` contains only 1s.
3.  `nums[current...right]` contains unprocessed elements (0s, 1s, or 2s).
4.  `nums[right+1...n-1]` contains only 2s.

*   **Initialization:** Before the loop (`left=0, current=0, right=n-1`), the regions for 0s, 1s, and 2s are empty, and the "unprocessed" region is the entire array. The invariant holds.
*   **Maintenance:** Each step of the loop (swapping a 0 to the left, a 2 to the right, or advancing past a 1) moves an element from the "unprocessed" region to one of the sorted regions, shrinking the unprocessed part while maintaining the invariant.
*   **Termination:** When the loop ends (`current > right`), the "unprocessed" region `nums[current...right]` is empty. The entire array now consists of the three sorted sections, satisfying the problem's requirements.

#### Follow-up 3: "Could you have used two pointers instead of three?"

Yes, it's possible, but less clean. For instance, you could use a pointer `i` that iterates through the array and another pointer `j` to mark the boundary of placed 0s. You would first move all 0s to the front. Then, you would start another pass from where the 0s ended to move all 1s. This effectively becomes a multi-pass solution (one pass for 0s, one pass for 1s). The three-pointer approach is superior because it sorts all elements in a single, elegant pass.