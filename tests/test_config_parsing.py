"""Tests for the shared config-parsing validators.

These back every config builder (schedule, estimation). The bool-rejection
cases matter: in Python ``True == 1``, so a careless ``isinstance(x, int)``
would accept ``True`` as a count.
"""

import pytest

from enfilera.config_parsing import positive_int, positive_number, section

# --- section -------------------------------------------------------------


def test_section_returns_the_table() -> None:
    assert section({"estimation": {"min_samples": 3}}, "estimation") == {
        "min_samples": 3
    }


def test_section_missing_raises_with_name() -> None:
    with pytest.raises(ValueError, match=r"\[estimation\]"):
        section({}, "estimation")


def test_section_non_mapping_raises() -> None:
    with pytest.raises(ValueError, match="missing"):
        section({"estimation": 42}, "estimation")


# --- positive_int --------------------------------------------------------


def test_positive_int_accepts_positive() -> None:
    assert positive_int(3, "min_samples") == 3


@pytest.mark.parametrize("bad", [0, -1])
def test_positive_int_rejects_non_positive(bad: int) -> None:
    with pytest.raises(ValueError, match="min_samples"):
        positive_int(bad, "min_samples")


def test_positive_int_rejects_bool() -> None:
    with pytest.raises(ValueError, match="min_samples"):
        positive_int(True, "min_samples")


def test_positive_int_rejects_float() -> None:
    with pytest.raises(ValueError, match="min_samples"):
        positive_int(3.0, "min_samples")


# --- positive_number -----------------------------------------------------


def test_positive_number_accepts_float_and_int() -> None:
    assert positive_number(3.0, "mad_k") == 3.0
    assert positive_number(3, "mad_k") == 3.0


@pytest.mark.parametrize("bad", [0, -0.5])
def test_positive_number_rejects_non_positive(bad: float) -> None:
    with pytest.raises(ValueError, match="mad_k"):
        positive_number(bad, "mad_k")


def test_positive_number_rejects_bool() -> None:
    with pytest.raises(ValueError, match="mad_k"):
        positive_number(True, "mad_k")
