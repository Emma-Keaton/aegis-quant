"""Utility functions for trade calculations.

Provides a simple linear scaling of trade size based on a base amount in USD and the signal confidence.
"""

def size_from_confidence(base: float, confidence: float) -> float:
    """Calculate trade size from a base trade amount (USD) and confidence percentage.

    The size is rounded to two decimal places.
    """
    if confidence < 0:
        confidence = 0
    if confidence > 100:
        confidence = 100
    size = round(base * confidence / 100, 2)
    return size
