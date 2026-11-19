"""Unit tests for selector canonicalization."""

import pytest

from app.services.selectors import canonicalize_selector


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('role=link[name="PRACTICE"]', 'role=link[name="PRACTICE"i]'),
        ('role=link[name="Practice"]', 'role=link[name="Practice"i]'),
        ('role=link[name="PRACTICE"i]', 'role=link[name="PRACTICE"i]'),
        ('role=link[name="PRACTICE"s]', 'role=link[name="PRACTICE"s]'),
        ('role=button[name="Submit"]', 'role=button[name="Submit"i]'),
        ('role=button[name="a\\"b"]', 'role=button[name="a\\"b"i]'),
        ("role=link[name='Practice']", "role=link[name='Practice'i]"),
        ("role=checkbox[name='x'][checked=true]", "role=checkbox[name='x'][checked=true]"),
        ("label=Username", "getByLabel:Username"),
        ('label="Some Label"', "getByLabel:Some Label"),
        ('internal:label="Username"i', "getByLabel:Username"),
        ("#row1 > input", "#row1 > input"),
        ("text=Foo", "text=Foo"),
        ("", ""),
        (None, None),
    ],
)
def test_canonicalize_selector(raw, expected):
    assert canonicalize_selector(raw) == expected


def test_canonicalize_selector_is_idempotent():
    raw = 'role=link[name="PRACTICE"]'
    assert canonicalize_selector(canonicalize_selector(raw)) == canonicalize_selector(raw)
