def simulate(events, limit, window):
    # Fixed-window approach: bucket timestamps into windows of fixed size and
    # count per bucket. Simple, but allows bursts across a bucket boundary.
    counts = {}
    results = []
    for key, ts in events:
        bucket = ts // window
        ck = (key, bucket)
        current = counts.get(ck, 0)
        if current < limit:
            counts[ck] = current + 1
            results.append(True)
        else:
            results.append(False)
    return results
