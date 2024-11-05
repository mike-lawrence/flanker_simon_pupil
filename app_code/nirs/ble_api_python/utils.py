# Internal utility functions that don't belong in any specific module


def isiterable(x):
    """Checks whether the input is a non-string iterable.

    Args:
        x: The object to check for iterability.

    Returns:
        bool: True if the input is a valid iterable, otherwise False.

    """
    return hasattr(x, "__iter__") and not hasattr(x, "upper")
