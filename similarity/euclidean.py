import numpy as np

def euclidean_distance(vector1, vector2):
    """
    Calculate the Euclidean distance between two vectors.

    Args:
        vector1 (list or np.ndarray): First vector.
        vector2 (list or np.ndarray): Second vector.

    Returns:
        float: Euclidean distance between the two vectors.
    """
    vector1 = np.array(vector1)
    vector2 = np.array(vector2)
    return np.sqrt(np.sum((vector1 - vector2) ** 2))