from collections import defaultdict, deque


def simulate(events, limit, window):
    """Sliding-window rate limiter using a per-key timestamp log.

    For each incoming event we evict timestamps older than `window` seconds,
    then admit the request only if fewer than `limit` remain in the window.
    This correctly handles bursts that straddle fixed-bucket boundaries.

    Time: O(n) amortized (each timestamp enqueued and dequeued once).
    Space: O(limit) per active key.
    """
    logs = defaultdict(deque)
    results = []
    for key, ts in events:
        q = logs[key]
        while q and q[0] <= ts - window:
            q.popleft()
        if len(q) < limit:
            q.append(ts)
            results.append(True)
        else:
            results.append(False)
    return results
