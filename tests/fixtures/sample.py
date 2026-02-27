#!/usr/bin/env python3
"""Sample Python script for FAR testing."""

def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"

def calculate_sum(numbers: list[int]) -> int:
    """Calculate sum of numbers."""
    return sum(numbers)

if __name__ == "__main__":
    print(greet("FAR"))
    print(f"Sum: {calculate_sum([1, 2, 3, 4, 5])}")
