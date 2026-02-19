import numpy as np

def manhattan_distance(vector1, vector2):
    """
    Calculate the Manhattan distance between two vectors.

    Args:
        vector1 (list or np.ndarray): First vector.
        vector2 (list or np.ndarray): Second vector.

    Returns:
        float: Manhattan distance between the two vectors.
    """
    vector1 = np.array(vector1)
    vector2 = np.array(vector2)
    return np.sum(np.abs(vector1 - vector2))