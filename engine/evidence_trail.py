"""
Evidence trail for street-level verdicts (VLA-15).

Client feedback (Vlado, 2026-07-06): a "street/assignment" verdict must never
be presented as a bare assertion — every such finding must show HOW we arrived
at it. The trail carries four elements, each Slovak and human-readable:

    vzn_citation      — which VZN street-list text assigns the street where
                        (verbatim ranges from skolske_obvody.vzn_street_ranges)
    register_state    — state of the address register for the affected streets
                        (Register adries + house_geocodes assignment table)
    geometry_evidence — which district geometry the address points fall into
    conclusion_sk     — human-readable conclusion (overlap/gap vocabulary only,
                        per client defect 8 — never "nesprávny obvod")

The dict is stored in verdict.provenance["evidence_trail"]; the findings_public
view sanitizes each field and exposes it to the UI (register + map legend).
"""

from __future__ import annotations

from ingest.supabase_client import query_sql


def _q(s: str) -> str:
    """Escape a value for single-quoted SQL literal (internal-trusted ids/names)."""
    return str(s).replace("'", "''")


def vzn_split_streets(district_id: str) -> list[dict]:
    """VZN street-list rows for streets this district SHARES with another
    district (the street is split between obvods by number ranges). These are
    exactly the streets where an assignment/geometry mismatch can arise.

    Returns rows: street, district_name, range_text, is_this (bool),
    deduplicated, capped to the first 3 shared streets so the citation stays
    readable (a street name repeated across rows = multiple VZN ranges).
    """
    rows = query_sql(f"""
        SELECT DISTINCT vsr.street,
               d.name AS district_name,
               COALESCE(NULLIF(vsr.raw_text, ''), 'celá ulica') AS range_text,
               (d.id::text = '{_q(district_id)}') AS is_this
        FROM skolske_obvody.vzn_street_ranges vsr
        JOIN skolske_obvody.districts d ON d.id = vsr.district_id
        WHERE vsr.street IN (
            SELECT street FROM skolske_obvody.vzn_street_ranges
            WHERE district_id = '{_q(district_id)}'
        )
        AND vsr.street IN (
            SELECT street FROM skolske_obvody.vzn_street_ranges
            GROUP BY street
            HAVING COUNT(DISTINCT district_id) > 1
        )
        ORDER BY vsr.street, d.name
    """)
    # Cap by street, preferring streets split between the FEWEST districts —
    # those read as the clearest two-way VZN splits (e.g. Šmeralova 1–23 vs
    # 27–29), while multi-way corner streets stay out of the citation.
    by_street: dict[str, list[dict]] = {}
    for r in rows:
        by_street.setdefault(r["street"], []).append(r)
    kept_streets = sorted(by_street, key=lambda s: (len(by_street[s]), s))[:3]
    return [r for s in sorted(kept_streets) for r in by_street[s]]


def format_vzn_citation(rows: list[dict]) -> str:
    """Verbatim VZN street-list citation: 'Ulica „rozsah" → obvod; …'."""
    if not rows:
        return (
            "Uličný zoznam VZN nedelí žiadnu ulicu tohto obvodu s iným obvodom "
            "(žiadna zdieľaná ulica s rozsahom čísel)."
        )
    parts = [
        f"{r['street']} „{r['range_text']}“ → {r['district_name']}"
        for r in rows
    ]
    return "Uličný zoznam VZN mesta Prešov: " + "; ".join(parts) + "."


def register_state_for_streets(streets: list[str]) -> str:
    """Register adries state for the affected streets (real counts)."""
    total = int(query_sql(
        "SELECT COUNT(*) AS n FROM skolske_obvody.register_adries"
    )[0]["n"])
    if not streets:
        return f"Register adries (mesto Prešov): {total} adries načítaných."
    street_list = ", ".join(f"'{_q(s)}'" for s in sorted(set(streets)))
    on_streets = int(query_sql(
        f"SELECT COUNT(*) AS n FROM skolske_obvody.register_adries "
        f"WHERE ulica IN ({street_list})"
    )[0]["n"])
    names = ", ".join(sorted(set(streets)))
    return (
        f"Register adries (mesto Prešov): {total} adries načítaných, "
        f"z toho {on_streets} na dotknutých uliciach ({names})."
    )


def build_s1_demo_trail(
    district_id: str, total: int, uncovered: int, overlap: int
) -> dict:
    """Trail for the DEMO Š1 verdict. The VZN citation and register counts are
    REAL data; the coverage counts (total/uncovered/overlap) are the demo input."""
    rows = vzn_split_streets(district_id)
    streets = sorted({r["street"] for r in rows})
    register = register_state_for_streets(streets)
    register += (
        f" Ukážkový vstup dema predpokladá úplné adresné pokrytie obvodu: "
        f"{total} adries."
    )

    geometry_parts = []
    if overlap:
        where = (
            f" (dotknuté zdieľané ulice: {', '.join(streets)})" if streets else ""
        )
        geometry_parts.append(
            f"{overlap} z {total} adresných bodov leží v geometrii iného "
            f"obvodu, než im určuje uličný zoznam VZN{where}"
        )
    if uncovered:
        geometry_parts.append(
            f"{uncovered} adresných bodov nepokrýva geometria žiadneho obvodu"
        )
    geometry = (
        "; ".join(geometry_parts) + "."
        if geometry_parts
        else f"Všetkých {total} adresných bodov leží v geometrii obvodu, "
             "ktorý im určuje uličný zoznam VZN."
    )

    if overlap or uncovered:
        conclusion = (
            "Uličný zoznam VZN delí zdieľané ulice medzi obvody podľa rozsahu "
            "čísel; časť adresných bodov padá do geometrie druhého obvodu. "
            "VZN priradenie a geometria obvodov si protirečia — prekryv "
            "priradenia / medzera v pokrytí (§ 44 ods. 1)."
        )
    else:
        conclusion = (
            "VZN priradenie a geometria obvodov sú v zhode — každá adresa je "
            "pokrytá práve jedným obvodom (§ 44 ods. 1)."
        )

    return {
        "vzn_citation": format_vzn_citation(rows),
        "register_state": register,
        "geometry_evidence": geometry,
        "conclusion_sk": conclusion,
    }


def build_s1_real_trail(
    district_id: str, ap_count: int, uncovered: int, multi: int
) -> dict:
    """Trail for the real address-point Š1 verdict."""
    rows = vzn_split_streets(district_id)
    streets = sorted({r["street"] for r in rows})
    geometry_parts = []
    if multi:
        geometry_parts.append(
            f"{multi} adresných bodov leží v geometrii viacerých obvodov (prekryv)"
        )
    if uncovered:
        geometry_parts.append(
            f"{uncovered} adresných bodov nepokrýva žiadny obvod (medzera v pokrytí)"
        )
    geometry = (
        "; ".join(geometry_parts) + "."
        if geometry_parts
        else f"Všetkých {ap_count} adresných bodov leží v geometrii práve jedného obvodu."
    )
    conclusion = (
        "Priestorové porovnanie adresných bodov s geometriou obvodov ukazuje "
        "nesúlad s uličným zoznamom VZN — prekryv priradenia alebo medzera "
        "v pokrytí (§ 44 ods. 1)."
        if (multi or uncovered)
        else "Adresné body a geometria obvodov sú v zhode (§ 44 ods. 1)."
    )
    return {
        "vzn_citation": format_vzn_citation(rows),
        "register_state": register_state_for_streets(streets)
        + f" Adresných bodov v teste: {ap_count}.",
        "geometry_evidence": geometry,
        "conclusion_sk": conclusion,
    }


def build_s1_proxy_trail(district_id: str, gap_pct: float, n_districts: int) -> dict:
    """Trail for the proxy (no address points) Š1 verdict — INCOMPLETE."""
    rows = vzn_split_streets(district_id)
    return {
        "vzn_citation": format_vzn_citation(rows),
        "register_state": (
            "Register adries pre tento test nie je k dispozícii (adresné body "
            "= 0) — per-adresné overenie neprebehlo."
        ),
        "geometry_evidence": (
            f"Geometrický proxy test: zjednotenie {n_districts} obvodov vs "
            f"hranica obce — medzera {gap_pct}% plochy obce."
        ),
        "conclusion_sk": (
            "Bez adresných bodov nemožno vyniesť verdikt o priradení ulíc — "
            "výsledok je NEÚPLNÝ, nie porušenie."
        ),
    }


def build_s2_trail(
    district_id: str, partners: list[str], shared_examples: list[str]
) -> dict:
    """Trail for the Š2 FAIL verdict (same full address claimed by 2+ districts).

    shared_examples: 'Ulica číslo' strings of the duplicated addresses.
    """
    streets = sorted({
        ex.rsplit(" ", 1)[0] for ex in shared_examples if " " in ex
    })
    # Is the duplicated street in the VZN street list at all? Cite verbatim.
    vzn_rows: list[dict] = []
    if streets:
        street_list = ", ".join(f"'{_q(s)}'" for s in streets)
        vzn_rows = query_sql(f"""
            SELECT vsr.street,
                   d.name AS district_name,
                   COALESCE(NULLIF(vsr.raw_text, ''), 'celá ulica') AS range_text,
                   (d.id::text = '{_q(district_id)}') AS is_this
            FROM skolske_obvody.vzn_street_ranges vsr
            JOIN skolske_obvody.districts d ON d.id = vsr.district_id
            WHERE vsr.street IN ({street_list})
            ORDER BY vsr.street, d.name
            LIMIT 12
        """)
    if vzn_rows:
        vzn_citation = format_vzn_citation(vzn_rows)
    else:
        names = ", ".join(streets) if streets else "—"
        vzn_citation = (
            f"Ulica ({names}) sa v uličnom zozname VZN nenachádza — priradenie "
            "dvom obvodom nemá oporu vo VZN texte."
        )

    examples = "; ".join(shared_examples[:5])
    register = (
        f"Tabuľka priradenia adries eviduje tú istú plnú adresu "
        f"(ulica + číslo) vo viacerých obvodoch: {examples}. "
        + register_state_for_streets(streets)
    )
    geometry = (
        "Adresný bod má jednu polohu — geometricky môže ležať len v jednom "
        f"obvode, priradený je však obvodom: {', '.join(partners)} aj tomuto obvodu."
    )
    conclusion = (
        "Tá istá plná adresa je priradená dvom obvodom rovnakého typu naraz — "
        "prekryv priradenia; § 44 ods. 1 a 7 pripúšťa pre adresu práve jeden "
        "obvod."
    )
    return {
        "vzn_citation": vzn_citation,
        "register_state": register,
        "geometry_evidence": geometry,
        "conclusion_sk": conclusion,
    }
