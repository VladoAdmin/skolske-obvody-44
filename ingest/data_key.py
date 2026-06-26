"""
Stable data_key catalogue — PRD §8 architecture.

Each dataset has a unique string key that:
  - Is stable across re-runs (idempotent ingestion)
  - Carries human-readable context about the source
  - Is referenced from verdicts for reproducibility

The key is used as the 'key' column in so_datasets table.
On re-ingest, the record is upserted (on_conflict=key).
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class DatasetKey:
    key: str           # stable identifier
    name: str          # human-readable
    source_url: str
    description: str
    completeness: int  # DAMA 1–10
    validity: int      # DAMA 1–10
    version: str = "1"


# --- Catalogue of all Sprint 1 datasets ---

DATASETS: dict[str, DatasetKey] = {
    "wfs_schools_psk": DatasetKey(
        key="wfs_schools_psk",
        name="Školské zariadenia PSK (Mapa regionálneho školstva CVTI)",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:mapa_regionalneho_skolstva",
        description="Všetky školy a školské zariadenia v PSK z WFS Geoportál PSK (vrátane vyuc_jazyk, pocet_ziakov). Zdroj: CVTI/Geoportál PSK.",
        completeness=9,
        validity=9,
    ),
    "wfs_municipalities_psk": DatasetKey(
        key="wfs_municipalities_psk",
        name="Administratívne hranice obcí PSK",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:admunit_municipalities",
        description="MultiPolygon geometria 665 obcí PSK, NUTS kód, IDN4. Zdroj: Geoportál PSK.",
        completeness=9,
        validity=9,
    ),
    "wfs_regions_psk": DatasetKey(
        key="wfs_regions_psk",
        name="Administratívna hranica Prešovského kraja",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:admunit_counties",
        description="Hranica PSK ako celku. Zdroj: Geoportál PSK.",
        completeness=9,
        validity=9,
    ),
    "wfs_mrk_atlas_2019": DatasetKey(
        key="wfs_mrk_atlas_2019",
        name="Atlas rómskych komunít 2019 (PSK)",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:wm_ark_municipal",
        description="Polygóny obcí s MRK komunitami 2019 (poc_2019, pod_2019, pocR_2019). Zdroj: Atlas rómskych komunít SR 2019.",
        completeness=7,
        validity=7,
    ),
    "wfs_mrk_buildings": DatasetKey(
        key="wfs_mrk_buildings",
        name="MRK obývané budovy (6 obcí PSK)",
        source_url="https://geopresovregion.sk/geoserver/wfs",
        description="Budovy v MRK lokalitách: Varhaňovce, Ostrovany, Krivany, Dlhé Stráže, Varadka, Čičava. Zdroj: RSM/Geoportál PSK.",
        completeness=7,
        validity=7,
    ),
    "wfs_pad_bus_stops": DatasetKey(
        key="wfs_pad_bus_stops",
        name="Zastávky PAD (prímestská autobusová doprava PSK)",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:autobusove_zastavky_pad",
        description="3172 zastávok PAD v PSK s vybavením a technickým stavom. Zdroj: Geoportál PSK.",
        completeness=7,
        validity=7,
    ),
    "wfs_rail_lines": DatasetKey(
        key="wfs_rail_lines",
        name="Železničná sieť PSK",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:zeleznice",
        description="Línie železničnej siete v PSK. Zdroj: Geoportál PSK.",
        completeness=8,
        validity=8,
    ),
    "wfs_rail_stops": DatasetKey(
        key="wfs_rail_stops",
        name="Železničné zastávky PSK",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:psk_zel_zastavky",
        description="127 železničných zastávok v PSK. Zdroj: Geoportál PSK.",
        completeness=8,
        validity=8,
    ),
    "wfs_roads_i": DatasetKey(
        key="wfs_roads_i",
        name="Cesty I. triedy PSK",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:cesty_1_triedy_ln",
        description="Línie ciest I. triedy v PSK. Zdroj: Geoportál PSK.",
        completeness=6,
        validity=6,
    ),
    "wfs_roads_ii": DatasetKey(
        key="wfs_roads_ii",
        name="Cesty II. triedy PSK",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:cesty_2_triedy_ln",
        description="Línie ciest II. triedy v PSK. Zdroj: Geoportál PSK.",
        completeness=6,
        validity=6,
    ),
    "wfs_roads_iii": DatasetKey(
        key="wfs_roads_iii",
        name="Cesty III. triedy PSK",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:cesty_3_triedy_ln",
        description="Línie ciest III. triedy v PSK. Zdroj: Geoportál PSK.",
        completeness=6,
        validity=6,
    ),
    "wfs_children_0_14": DatasetKey(
        key="wfs_children_0_14",
        name="Veková štruktúra 0–14 rokov (mestá/obce PSK)",
        source_url="https://geopresovregion.sk/geoserver/wfs?SERVICE=WFS&REQUEST=GetFeature&TYPENAMES=geo-psk:so_age_structure_0_14_municipalities",
        description="Počty detí 0–14 rokov podľa obcí PSK, časový rad 1996–_last. Zdroj: ŠÚSR/Geoportál PSK.",
        completeness=7,
        validity=7,
    ),
    "vzn_presov_1_2023": DatasetKey(
        key="vzn_presov_1_2023",
        name="VZN Mesta Prešov č. 1/2023 — školské obvody",
        source_url="https://www.presov.sk/",
        description="Všeobecne záväzné nariadenie č. 1/2023 o určení školských obvodov základných škôl v Prešove. Parsovaný text → geometria obvodov (q6). Zdroj: Mesto Prešov.",
        completeness=6,
        validity=6,
    ),
    "mvsr_register_adries_psk": DatasetKey(
        key="mvsr_register_adries_psk",
        name="Register adries MV SR — adresné body PSK",
        source_url="https://www.minv.sk/?register-adries",
        description="Adresné body (súpisné čísla + GPS) pre obce PSK. Zdroj: MV SR, Register adries. TVRDÁ ZÁVISLOSŤ pre Š1 a P-b.",
        completeness=9,
        validity=9,
    ),
}


def get_dataset_record(key: str, fetched_at: Optional[str] = None) -> dict:
    """
    Build the DB record for so_datasets table.
    fetched_at: ISO datetime string; defaults to now.
    """
    from datetime import datetime
    ds = DATASETS[key]
    return {
        "key": ds.key,
        "name": ds.name,
        "source_url": ds.source_url,
        "description": ds.description,
        "completeness": ds.completeness,
        "validity": ds.validity,
        "version": ds.version,
        "fetched_at": fetched_at or datetime.utcnow().isoformat() + "Z",
        "status": "active",
    }
