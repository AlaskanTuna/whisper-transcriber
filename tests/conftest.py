"""Shared fixtures. Nothing here needs a Whisper model or a Gemini key."""

import pytest


@pytest.fixture
def segments():
    """A small, well-behaved segment list."""
    return [
        {"start": 0.0, "end": 2.5, "text": " Hello there "},
        {"start": 2.5, "end": 6.0, "text": "Second line"},
        {"start": 6.0, "end": 9.0, "text": "Third line"},
    ]


@pytest.fixture
def long_segments():
    """Thirty minutes of half-minute segments, for chunking tests."""
    return [
        {"start": float(i * 30), "end": float(i * 30 + 29), "text": f"line {i}"}
        for i in range(60)
    ]
