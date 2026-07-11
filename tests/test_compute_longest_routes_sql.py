"""
VLA-17 — SQL-construction regression guard for scripts/compute_longest_routes.py.

WHY this matters:
  External review (GPT-5.5, 2026-07-10, PR #4) flagged _dq() and the SQL
  built in _load_street_geocode_candidates / _load_shared_municipality_candidates
  / _replace_district_routes as SQL-injection risk: values were spliced into
  f-strings via fixed, predictable dollar-quote tags (or bare '...' quoting
  for district_id), so a value containing that tag or an unescaped quote
  could break out of its literal. The fix gives every _dq() call a fresh
  random tag. These tests fail if that guarantee regresses — e.g. if a
  future edit goes back to a fixed/predictable tag or reintroduces bare
  string interpolation of a value into a SQL literal.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import compute_longest_routes as clr


# ------------------------------------------------------------------ _dq() itself

def test_dq_round_trips_the_value_between_a_matching_tag_pair():
    out = clr._dq("Hlavná 12")
    # Find the tag: dollar-quote syntax is $tag$...$tag$, tag here is
    # "__q<hex>__" — recover it from the known prefix/suffix shape.
    assert out.startswith("$__q")
    tag_end = out.index("__$") + len("__$")
    tag = out[:tag_end]
    assert out == f"{tag}Hlavná 12{tag}"


def test_dq_never_reuses_the_same_tag_across_calls():
    # The old bug: a fixed short tag (e.g. "$__ol__$") reused on every call
    # meant a value containing that literal tag could break the quoting.
    # A fresh random tag per call is what closes that hole — assert it.
    tags = set()
    for _ in range(50):
        out = clr._dq("x")
        tag_end = out.index("__$") + len("__$")
        tags.add(out[:tag_end])
    assert len(tags) == 50


def test_dq_defeats_a_value_containing_a_previously_used_fixed_tag():
    # Simulates the exact attack the old fixed-tag scheme was vulnerable to:
    # a value that itself contains the delimiter tag text used elsewhere in
    # the old code (e.g. "$__ol__$") must not be able to terminate the
    # quoting early, because the fresh tag is random and independent of it.
    payload = "innocent$__ol__$'; DROP TABLE skolske_obvody.districts; --"
    out = clr._dq(payload)
    tag_end = out.index("__$") + len("__$")
    tag = out[:tag_end]
    assert out == f"{tag}{payload}{tag}"
    # The payload must appear exactly once, fully inside the tag pair — not
    # split by an early-matching tag occurrence.
    assert out.count(payload) == 1


def test_dq_preserves_unescaped_single_quotes_verbatim():
    # Dollar-quoting must make quote characters inert without any escaping
    # transform (unlike '...'-style literals, which need quote-doubling).
    payload = "O'Brien Street ' OR '1'='1"
    out = clr._dq(payload)
    assert payload in out
    tag_end = out.index("__$") + len("__$")
    tag = out[:tag_end]
    assert out == f"{tag}{payload}{tag}"


def test_dq_raises_instead_of_silently_reusing_a_colliding_tag():
    # If tag generation could never find a collision-free tag (forced here
    # via a monkeypatched uuid4), _dq must fail loudly rather than emit SQL
    # that a crafted value could break out of.
    fixed_hex = "deadbeef"
    payload = f"$__q{fixed_hex}__$"  # pre-seed the value with the tag uuid4 will "generate"

    class _FixedUUID:
        hex = fixed_hex

    with mock.patch.object(clr.uuid, "uuid4", return_value=_FixedUUID()):
        try:
            clr._dq(payload)
            raised = False
        except ValueError:
            raised = True
    assert raised


# ------------------------------------------------- query-builder call sites

def test_street_geocode_candidates_district_id_is_dollar_quoted_not_spliced():
    malicious_id = "x'; DROP TABLE skolske_obvody.street_geocodes; --"
    captured = {}

    def fake_query_sql(sql):
        captured["sql"] = sql
        return []

    with mock.patch.object(clr, "query_sql", fake_query_sql):
        clr._load_street_geocode_candidates(malicious_id)

    sql = captured["sql"]
    # The old vulnerable form spliced the raw value between bare quotes.
    assert f"'{malicious_id}'" not in sql
    # The value must instead be present, whole, inside a dollar-quote tag pair.
    assert malicious_id in sql


def test_shared_municipality_in_clause_dollar_quotes_each_name():
    malicious_name = "Dulová Ves'); DROP TABLE skolske_obvody.municipalities; --"
    captured = {}

    def fake_query_sql(sql):
        captured["sql"] = sql
        return []

    with mock.patch.object(clr, "query_sql", fake_query_sql):
        clr._load_shared_municipality_candidates("Test District", [malicious_name])

    sql = captured["sql"]
    assert f"'{malicious_name}'" not in sql
    assert malicious_name in sql
    assert "unaccent($__q" in sql
