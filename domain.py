"""Shared domain types used across layers."""
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class Fact:
    text: str
    major: bool = False


class Verdict(StrEnum):
    correct = "correct"
    partial = "partial"
    incorrect = "incorrect"
