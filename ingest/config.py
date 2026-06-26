"""
Ingest configuration — loads env, validates required vars.

Schema: tables live in the skolske_obvody custom schema.
All writes go through f2_exec_sql / f2_query_sql RPC bridges
(PostgREST does not expose the skolske_obvody schema directly).
"""

import os
import sys
from datetime import date

# --- Required ---
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# --- Optional ---
GOOGLE_MAPS_API_KEY: str = os.environ.get("GOOGLE_MAPS_API_KEY", "")
ROUTING_URL: str = os.environ.get("ROUTING_URL", "http://localhost:5000")

# --- Schema config ---
# Tables live in the 'skolske_obvody' schema, accessed via RPC bridge.
SCHEMA_NAME: str = "skolske_obvody"
TABLE_PREFIX: str = ""  # no prefix — direct table names

# --- WFS sources ---
WFS_BASE_URL = "https://geopresovregion.sk/geoserver/wfs"
WFS_VERSION = "2.0.0"
WFS_OUTPUT_FORMAT = "application/json"
WFS_MAX_FEATURES = 10000  # safety cap per request

# Layer names
WFS_LAYER_SCHOOLS = "geo-psk:mapa_regionalneho_skolstva"
WFS_LAYER_MUNICIPALITIES = "geo-psk:admunit_municipalities"
WFS_LAYER_REGIONS = "geo-psk:admunit_counties"
WFS_LAYER_MRK_ATLAS = "geo-psk:wm_ark_municipal"
WFS_LAYER_MRK_VARHANOVCE = "geo-psk:rsm_varhanovce_budovy"
WFS_LAYER_MRK_OSTROVANY = "geo-psk:rsm_ostrovany_budovy"
WFS_LAYER_MRK_KRIVANY = "geo-psk:rsm_krivany_budovy"
WFS_LAYER_MRK_DLHE_STRAZE = "geo-psk:rsm_dlhe_straze_budovy"
WFS_LAYER_MRK_VARADKA = "geo-psk:rsm_varadka_budovy"
WFS_LAYER_MRK_CICAVA = "geo-psk:rsm_cicava_budovy"
WFS_LAYER_PAD_BUS_STOPS = "geo-psk:autobusove_zastavky_pad"
WFS_LAYER_RAIL_LINES = "geo-psk:zeleznice"
WFS_LAYER_RAIL_STOPS = "geo-psk:psk_zel_zastavky"
WFS_LAYER_ROADS_I = "geo-psk:cesty_1_triedy_ln"
WFS_LAYER_ROADS_II = "geo-psk:cesty_2_triedy_ln"
WFS_LAYER_ROADS_III = "geo-psk:cesty_3_triedy_ln"
WFS_LAYER_CHILDREN_0_14 = "geo-psk:so_age_structure_0_14_municipalities"

# --- Data provenance dates ---
WFS_SOURCE_DATE = date.today().isoformat()  # fetched today
VZN_SOURCE_DATE = "2023-01-01"  # VZN 1/2023 effective date

# --- Geometry quality (DATA_INVENTORY_PSK.csv q-ratings) ---
QUALITY_SCHOOLS_WFS = 9
QUALITY_MUNICIPALITIES = 9
QUALITY_REGIONS = 9
QUALITY_MRK_ATLAS = 7
QUALITY_MRK_BUILDINGS = 7
QUALITY_PAD_STOPS = 7
QUALITY_RAIL = 8
QUALITY_ROADS = 6
QUALITY_CHILDREN_0_14 = 7
QUALITY_VZN_GEOMETRY = 6  # derived from PDF text, q6
QUALITY_ADDRESS_POINTS = 9  # Register adries MV SR


def validate_config() -> None:
    """Raise if required env vars are missing."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        print(f"ERROR: Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        print("Copy env.example.txt to .env.local and set the values.", file=sys.stderr)
        sys.exit(1)
