import numpy as np

def minkowski_distance(vector1, vector2, p):
    """
    Calculate the Minkowski distance between two vectors.

    Args:
        vector1 (list or np.ndarray): First vector.
        vector2 (list or np.ndarray): Second vector.
        p (int): Order of the Minkowski distance.

    Returns:
        float: Minkowski distance between the two vectors.
    """
    vector1 = np.array(vector1)
    vector2 = np.array(vector2)
    return np.sum(np.abs(vector1 - vector2) ** p) ** (1 / p)