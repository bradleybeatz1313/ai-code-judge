def two_sum(nums, target):
    """Return indices of the two values summing to target.

    Uses a single pass with a hash map from value -> index, giving O(n) time
    and O(n) space. For each element we check whether its complement has
    already been seen.
    """
    seen = {}
    for index, value in enumerate(nums):
        complement = target - value
        if complement in seen:
            return [seen[complement], index]
        seen[value] = index
    return []
