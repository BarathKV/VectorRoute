import numpy as np

def dot_product(vector1, vector2):
    """
    Calculate the dot product of two vectors.

    Args:
        vector1 (list or np.ndarray): First vector.
        vector2 (list or np.ndarray): Second vector.

    Returns:
        float: Dot product of the two vectors.
    """
    vector1 = np.array(vector1)
    vector2 = np.array(vector2)
    return np.dot(vector1, vector2)