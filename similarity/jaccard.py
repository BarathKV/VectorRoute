def jaccard_similarity(set1, set2):
    """
    Calculate the Jaccard similarity between two sets.

    Args:
        set1 (set): First set.
        set2 (set): Second set.

    Returns:
        float: Jaccard similarity between the two sets.
    """
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0.0