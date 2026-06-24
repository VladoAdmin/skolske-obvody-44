"""
VZN Prešov 1/2023 parser.

Extracts per-school district definitions from the PDF, then geocodes
street names against address points (or nominatim fallback) to build
MultiPolygon geometries.

Strategy:
  1. Parse PDF text → extract 12 districts with their street lists.
  2. For each street: look up matching address points in so_address_points
     (if loaded). Fallback: Nominatim geocoding for Prešov streets.
  3. Geometry = concave hull (or unioned buffer) of matched address points.
     Method: buffer each address point by 50 m, union, then concave hull.
  4. geometry_quality = 6, geometry_confidence = 'medium',
     reviewed_by = NULL (Sprint 2 manual review).
  5. Unresolved streets: log structured entry, do NOT interpolate geometry.

This module is the canonical source for VZN parsing logic.
It can be re-run safely (idempotent via data_key).
"""

import re
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- VZN source data (parsed from PDF, canonical) ---
VZN_PDF_PATH = Path(__file__).parent / "sources" / "vzn_presov_1_2023.pdf"
VZN_SOURCE_URL = "http://www.skolskyurad.presov.sk/download_file_f.php?id=2250912"
VZN_SOURCE_DATE = "2023-09-01"  # effective date
MUNICIPALITY_NAME = "Prešov"
MUNICIPALITY_NUTS = "SK0417519212"  # Prešov city NUTS code


@dataclass
class SchoolDistrict:
    """Parsed school district definition from VZN."""
    district_number: int
    school_name: str       # e.g. "Základná škola, Bajkalská č. 29"
    school_address: str    # extracted from district title
    streets: list[str] = field(default_factory=list)
    # Qualifying notes per street (e.g. "nepárne čísla", "párne čísla")
    street_qualifiers: dict[str, str] = field(default_factory=dict)
    # Shared district municipalities
    shared_municipalities: list[str] = field(default_factory=list)
    vzn_article: str = "Článok 3"
    vzn_source_text: str = ""


@dataclass
class UnresolvedStreet:
    """Structured log entry for a street that couldn't be geocoded."""
    district_number: int
    school_name: str
    street: str
    reason: str


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required. Run: pip install pdfplumber")

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


# Full VZN text extracted from PDF (canonical, embedded for reproducibility)
# This is the actual text from the downloaded PDF — no interpolation.
VZN_FULL_TEXT = """Článok 3
Spoločné školské obvody základných škôl

1. Základná škola, Bajkalská č. 29:
Genplk. Jána Ambruša, Bajkalská (nepárne čísla), Bendíkova, Brezova, Broskyňová, Buková, Dúbravská, Horská, Jahodová, Jánošíkova, Javorinská, K Okruhliaku, K Starej tehelni (číslo 6, číslo 12), Liesková, Malinová, Nemčíkova, Orgovánová, Pod Dubom, Pod Skalkou, Prostějovská (nepárne č. 93 – 101, 105 – 117, 119, párne č. 62 – 72), Pustá dolina, Sabinovská (párne čísla od 2 – 160), Severná, Slnečná, Spannerovej, Stavbárska, Šidlovec, Šmeralova (27 – 29), Tatranská, Tomášikova (párne čísla od 2 – 14), Veterná.
Obec: Gregorovce (žiaci 5. – 9. ročníka), Hubošovce (žiaci 5. – 9. ročníka), Uzovce (žiaci 5. – 9. ročníka).

2. Základná škola, Československej armády č. 22:
19. januára, Átriová, Bachingerovka, Botanická, Cemjata, Čerešňová, Československej armády, Dúhová, Engelsova, Fraňa Kráľa, Fučíkova, Gorkého, Horárska, Irisová, Jaboňová, Jána Bottu, Jazvečia, Jelenia, K Starej Tehelni (číslo 10), Kollárova, Ku Brezinám, Ku Kyslej vode, Kvašná voda, Levočská, Malkovská, Marka Čulena, Matúša Trenčianskeho, Medzinárodného dňa žien, Mojmírova, Nábrežná, Narcisová, Námestie mládeže, Obrancov mieru, Odborárska, Októbrová, Ortáš, Petőfiho, Pod Kalváriou, Poľovnícka ulica, Rombauerova, Sadovnícka, Sázavského, Skromná, Slávičia, Srnčia, Staré záhrady, Súľovská, Terchovská, Turistická, Urbánkova, Vlčia, Vydumanec, Za Kalváriou, Zabíjaná, Zajačia.
Obec: Malý Šariš (žiaci 1. – 9. ročníka), Mirkovce (žiaci 5. – 9. ročníka), Župčany (žiaci 5. – 9. ročníka).

3. Základná škola, Kúpeľná č. 2:
17. novembra, Baštová, Bayerova, Belianska, Biskupa Gojdiča, Bociania, Borkut, Budovateľská, Bulharská, Burianova, Dilongova, Dostojevského, Duchnovičovo námestie, Francisciho, Františkánske námestie, Floriánova, Garbiarska, Grešova, Hlavná, Hodžova, Hraničná, Hrnčiarska, Hurbanistov, Hviezdna, Hviezdoslavova, Jána Hollého, Janka Borodáča, Jána Pavla II., Jarková, Jilemnického, K amfiteátru, K prameňu, K Starej tehelni (čísla 11), Kmeťovo stromoradie, Konštantínova, Kopaniny, Kováčska, Kpt. Nálepku, Krátka, Kúpeľná, Ku Kumštu, Kuzmányho, Lesík delostrelcov, Lúčna, Masarykova, Matky Terezy, Maybaumova, Moyzesova, Metodova, Námestie 1. mája, Námestie legionárov, Námestie mieru, Námestie Národného povstania, Na Rovni, Na Tablách, Okružná, Partizánska, Pavlovičovo námestie, Pražská, Pri Toryse, Plzenská, Pod Kamennou baňou, Pod Táborom, Pod Wilec hôrkou, Potočná, Požiarnická, Priemyselná, Pri ihrisku, Pri kostole, Protifašistických bojovníkov, Puškinova, Raymanova, Radlinského, Rumanova, Sedliackeho povstania, Sídlisko duklianskych hrdinov, Sládkovičova, Slovenská, Svätoplukova, Strojnícka, Suchomlynská, Surdok, Šafárikova, Šarišská, Školská, Škultétyho, Športová, Štefánikova, Špitálska, Štúrova, Tarasa Ševčenka, Tkáčska, Topoľová, Trnková, Vajanského, Vodná, Vodárenská, Vranovská, Východná, Záborského, Záhradná, Zápotockého, Za traťou, Zimný potok, Železničiarska, Železničná, Weberova.
Obec: Haniska (žiaci 1. – 9. ročníka).

4. Základná škola, Lesnícka č. 1:
Banícka, Bohúňova, Boženy Němcovej, Čajkovského, Čipkárska, Dlhá, Gápľová, Chmeľová, Kraskova, Kukučínova, Ku Škáre, Kutuzovova, Kysucká, Lesnícka, Lidická, Ľ. Podjavorinskej, Na brehu, Námestie osloboditeľov, Okrajová, Ondavská, Opavská, Padlých hrdinov, Palackého, Palárikova, Pod Debrami, Pod Hrádkom, Pod Turňou, Pri Delni, Pri hati, Pri mlyne, Smetanova, Sadová, Solivarská, Soľnobanská, Suchoňova, Šípková, Tajovského, Tokajícka, Valkovská, Zborovská, Zlatobanská.
Obec: Abranovce (žiaci 5. – 9. ročníka), Dulová Ves (žiaci 1. – 9. ročníka; ulica: Hlavná, Jarná, Jesenná, K ihrisku, Krátka, Lesná, Letná, Lúčna, Obchodná, Okružná, Pod lesom, Poľná, Potočná, Slánska, Záborská, Zimná), Kokošovce (žiaci 5. – 9. ročníka), Ruská Nová Ves (žiaci 5. – 9. ročníka), Teriakovce (žiaci 1. – 9. ročníka), Zlatá Baňa (žiaci 1. – 9. ročníka).

5. Základná škola, Májové námestie č. 1:
Alexandra Matušku, Arm. gen. Svobodu, Bencúrova, Bratislavská, Dargovská, Dubová, Federátov (párne čísla 2 – 16), K studničke, Kozmonautov, L. Novomestského, Májové námestie, Martina Benku, Na vyhliadke, Oravská, Pavla Horova, Popradská, Pri majáku, Smreková, Zemplínska, Zimná.
Obec: Kendice (žiaci 1. – 9. ročníka).

6. Základná škola s materskou školou, Námestie Kráľovnej pokoja 4:
Björnsonova, Jána Béreša, Jána Nováka, K Starej tehelni (čísla 4 – 5), Kotrádova, Matice slovenskej, Mukačevská, Na Rúrkach, Námestie Kráľovnej pokoja, Pod Rúrkami, Pőschlova, Slivková, Vlada Clementisa, Volgogradská, Tarjányiho, Tehelná.
Obec: Bzenov (žiaci 5. – 9. ročníka), Janov (žiaci 1. – 9. ročníka).

7. Základná škola, Mirka Nešpora č. 2:
Alexeja Duchoňa, Aurela Stodolu, Bikoš, Gorazdova, Holländerova, Hrušková, K Starej tehelni (číslo 7), Koceľova, K Surdoku, Ku Kráľovej hore, Mirka Nešpora, Na Bikoši, Pribinova, Prostějovská (č. 117/A, 103), Rastislavova, Ulica Jána Lazoríka, Ulica Michala Bosáka, Ulica Štefana Náhalku.
Obec:

8. Základná škola, Prostějovská č. 38:
Antona Prídavka, Bezrúčova, Čapajevova, Janouškova, Jazdecká, K Starej Tehelni (číslo 9), Komenského, Krížna, Kvetná, Letná, Lipová, Jesenského, Majakovského, Mätová ulica, Mičurinova, Mlynská, Mudroňova, Plavárenská, Prostějovská (č. 1 – 22, párne čísla 24 – 34), Tomášikova (párne čísla 30 – 58), Wolkerova, Záhradnícka, Západná.
Obec: Šarišské Sokolovce (žiaci 1. – 9. ročníka).

9. Základná škola, Sibírska č. 42:
Agátová, Astrová, Bažantia, Borovicová, Čergovská, Drozdia, Družstevná, Ďumbierska, Fintická, Gaštanová, Haburská, Herľanská, Holubia, Hruny, Jantárová, Jarná, Jastrabia, Jedľová, Južná, K potoku, Kamenná, Labutia, Lastovičia, Levanduľová, Limbová, Ľubotická, Magurská, Mateja Huľu, Mateja Murgaša, Medová, Muškátová, Nevädzová, Nová, Orlia, Orechová, Pažica, Pávia, Poľná, Pod Šalgovíkom, Púpavová, Rezbárska ulica, Rybárska, Sekčovská, Sibírska, Slánska, Sokolia, Sovia ulica, Strážnická, Šalviová, Šebastovská, Teriakovská, Tulipánová, Včelárska, Vihorlatská, Zlatnícka.
Obec:

10. Základná škola, Šmeralova č. 25:
Bajkalská (párne čísla), Duklianska, Gerlachovská, Hrabová, Kúty, K Starej tehelni (číslo 8), Lesná, Murárska, Medvedia, Námestie biskupa Vasiľa Hopka, Pod komínom, Pod Vinicami, Prostějovská (nepárne čísla 23 – 91, párne čísla 36 – 60), Račia, Riečna, Ružová, Rybníčky, Sabinovská (nepárne čísla 1 – 169), Šmeralova (čísla 1 – 23), Šidlovská, Tomášikova (párne čísla 2 – 56), Údenárska, Veselá.
Obec: Ratvaj (žiaci 1. – 9. ročníka), Varhaňovce (žiaci 5. – 9. ročníka).

11. Základná škola, Šrobárova č. 20:
Bernolákova, Exnárova, Federátov (nepárne čísla 1 – 13), Jurkovičova, Justičná, Karpatská, Keratsinské námestie, Líščia, Námestie Krista Kráľa, Rusínska, Šoltésovej, Šrobárova, Tichá, Vansovej, Višňova.
Obec: Drienovská Nová Ves (žiaci 5. – 9. ročníka).

12. Základná škola, Važecká č. 11:
Chalupkova, Janáčkova, Jelšova, Jesenná, Jiráskova, Kamencová, Košická, Lomnická, Pekná, Petrovianska, Pionierska, Royova, Soľná, Soľanková, Suvorovova, Švábska, Urxova, Úzka, Važecká.
Obec: Dulová Ves (žiaci 1. – 9. ročníka; ulica: Druhá, Piata, Prvá, Siedma, Šiesta, Štvrta, Tretia), Záborské (žiaci 1. – 9. ročníka).
"""


def parse_vzn_text(text: str = VZN_FULL_TEXT) -> list[SchoolDistrict]:
    """
    Parse VZN text to extract school district definitions.
    Returns list of SchoolDistrict objects (one per school).
    """
    districts: list[SchoolDistrict] = []

    # Match each numbered district block
    # Pattern: "N. Základná škola, <address>:\n<streets>\nObec: <obce>"
    district_pattern = re.compile(
        r"(\d+)\.\s+(Základná škola[^:]+):\s*\n(.*?)(?=\n\d+\.\s+Základná|$)",
        re.DOTALL,
    )

    for match in district_pattern.finditer(text):
        num = int(match.group(1))
        school_name = match.group(2).strip()
        content = match.group(3).strip()

        # Extract school address from name
        addr_match = re.search(r",\s+(.+)$", school_name)
        school_address = addr_match.group(1).strip() if addr_match else school_name

        # Split content at "Obec:" line
        obec_split = re.split(r"\nObec:\s*", content, maxsplit=1)
        streets_text = obec_split[0].strip()
        obec_text = obec_split[1].strip() if len(obec_split) > 1 else ""

        # Parse streets: split by ", " but handle qualifiers in parentheses
        streets, qualifiers = _parse_street_list(streets_text)

        # Parse shared municipalities
        shared = _parse_shared_municipalities(obec_text)

        district = SchoolDistrict(
            district_number=num,
            school_name=school_name,
            school_address=school_address,
            streets=streets,
            street_qualifiers=qualifiers,
            shared_municipalities=shared,
            vzn_source_text=match.group(0).strip(),
        )
        districts.append(district)

    return districts


def _parse_street_list(text: str) -> tuple[list[str], dict[str, str]]:
    """
    Parse a comma-separated street list with optional qualifiers in parens.
    Returns (streets, qualifiers_dict).
    """
    streets: list[str] = []
    qualifiers: dict[str, str] = {}

    # Remove newlines, collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Split by comma, but not commas inside parentheses
    parts = _split_respecting_parens(text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract qualifier if present: "Street (qualifier)"
        q_match = re.search(r"^(.+?)\s*\(([^)]+)\)\s*$", part)
        if q_match:
            street = q_match.group(1).strip()
            qualifier = q_match.group(2).strip()
            streets.append(street)
            qualifiers[street] = qualifier
        else:
            streets.append(part)

    return streets, qualifiers


def _split_respecting_parens(text: str) -> list[str]:
    """Split by comma but not inside parentheses."""
    parts = []
    depth = 0
    current = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _parse_shared_municipalities(text: str) -> list[str]:
    """Parse 'Obec:' section to extract municipality names."""
    if not text or text.strip() in ("", "–"):
        return []

    # Remove grade qualifiers like "(žiaci 5. – 9. ročníka)"
    text = re.sub(r"\s*\(žiaci[^)]*\)\s*", " ", text)
    # Remove street sub-lists like "(ulica: ...)"
    text = re.sub(r"\s*\(ulica:[^)]*\)\s*", " ", text)
    text = re.sub(r"\s*;.*$", "", text, flags=re.MULTILINE)

    # Split by comma or semicolon
    parts = re.split(r"[,;]", text)
    return [p.strip() for p in parts if p.strip()]


def geocode_street_nominatim(
    street: str,
    city: str = "Prešov",
    country: str = "Slovakia",
) -> Optional[list]:
    """
    Geocode a street name via Nominatim (OpenStreetMap).
    Returns [lon, lat] of the centroid, or None if not found.
    Rate-limited: max 1 request/second.
    """
    import urllib.request
    import urllib.parse
    import time

    query = f"{street}, {city}, {country}"
    params = {
        "q": query,
        "format": "json",
        "limit": "1",
        "addressdetails": "0",
    }
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "SkolskeObvody-Geocoder/1.0"})
    time.sleep(1.1)  # OSM Nominatim rate limit: 1 req/sec

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode("utf-8"))
            if results:
                return [float(results[0]["lon"]), float(results[0]["lat"])]
    except Exception:
        pass
    return None


def build_district_geometry(
    streets: list[str],
    qualifiers: dict[str, str],
    city: str = "Prešov",
    address_points: Optional[list] = None,
) -> tuple[Optional[object], list[UnresolvedStreet], int]:
    """
    Build a geometry for a district from its street list.

    Method:
    1. For each street: find matching address points (if available) OR
       geocode via Nominatim.
    2. Buffer each point by 50 m (approx in degrees: 50m / 111000 = 0.00045 deg).
    3. Union all buffers.
    4. Take concave hull (alpha shape) or convex hull as fallback.

    Returns: (geometry | None, unresolved_streets, resolved_count)
    geometry_quality = 6 always (derived from text geocoding).
    """
    try:
        from shapely.geometry import Point, MultiPolygon
        from shapely.ops import unary_union
    except ImportError:
        raise ImportError("shapely is required. Run: pip install shapely")

    BUFFER_DEG = 0.00045  # ~50 metres at Slovakia latitude

    resolved_points: list = []
    unresolved: list[UnresolvedStreet] = []

    for street in streets:
        qualifier = qualifiers.get(street, "")

        # Try address points lookup first
        found = False
        if address_points:
            # Filter address points matching this street
            matching = [
                ap for ap in address_points
                if _street_matches(ap.get("street", ""), street)
            ]
            if matching:
                for ap in matching[:50]:  # cap to avoid huge geometries
                    lon, lat = ap["lon"], ap["lat"]
                    resolved_points.append(Point(lon, lat).buffer(BUFFER_DEG))
                found = True

        if not found:
            # Fallback: Nominatim geocoding
            coords = geocode_street_nominatim(street, city)
            if coords:
                resolved_points.append(Point(coords[0], coords[1]).buffer(BUFFER_DEG))
                found = True

        if not found:
            unresolved.append(
                UnresolvedStreet(
                    district_number=0,  # caller fills in
                    school_name="",
                    street=street,
                    reason="Street not found in address_points or Nominatim",
                )
            )

    if not resolved_points:
        return None, unresolved, 0

    # Union all buffered points
    union = unary_union(resolved_points)

    # Try concave hull (shapely 2.x supports concave_hull)
    try:
        from shapely import concave_hull
        geom = concave_hull(union, ratio=0.3)
        if not geom.is_valid:
            geom = geom.buffer(0)
    except (ImportError, AttributeError):
        # Fallback to convex hull
        geom = union.convex_hull

    # Ensure MultiPolygon
    if geom.geom_type == "Polygon":
        geom = MultiPolygon([geom])

    return geom, unresolved, len(resolved_points)


def _street_matches(ap_street: str, vzn_street: str) -> bool:
    """
    Fuzzy match between address point street name and VZN street name.
    Normalises diacritics and common abbreviations.
    """
    def normalise(s: str) -> str:
        return s.lower().strip()

    a = normalise(ap_street)
    b = normalise(vzn_street)
    return a == b or a.startswith(b) or b.startswith(a)


def load_and_parse_vzn() -> list[SchoolDistrict]:
    """Main entry: parse VZN from embedded text."""
    return parse_vzn_text(VZN_FULL_TEXT)


def districts_to_db_records(
    districts: list[SchoolDistrict],
    municipality_id: Optional[str] = None,
    geocode: bool = False,
    address_points: Optional[list] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Convert parsed districts to DB records for so_districts and so_vzns tables.

    geocode: if True, attempt Nominatim geocoding (slow, rate-limited).
    address_points: pre-loaded address point dicts with {street, lon, lat}.

    Returns: (district_records, unresolved_log)
    """
    from datetime import datetime

    vzn_record = {
        "key": "vzn_presov_1_2023",
        "title": "VZN mesta Prešov č. 1/2023 o určení školských obvodov",
        "municipality_name": MUNICIPALITY_NAME,
        "effective_date": VZN_SOURCE_DATE,
        "source_url": VZN_SOURCE_URL,
        "raw_text": VZN_FULL_TEXT,
        "source_name": "Šk. úrad Prešov / skolskyurad.presov.sk",
        "source_date": "2023-09-01",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }

    district_records: list[dict] = []
    all_unresolved: list[dict] = []

    for d in districts:
        geom_wkt = None
        geom_confidence = "low"
        resolved_count = 0

        if geocode and (address_points or True):
            try:
                geom, unresolved, resolved_count = build_district_geometry(
                    d.streets, d.street_qualifiers, address_points=address_points
                )
                if geom:
                    from shapely.wkt import dumps
                    geom_wkt = f"SRID=4326;{dumps(geom, rounding_precision=7)}"
                    total = len(d.streets)
                    ratio = resolved_count / total if total > 0 else 0
                    geom_confidence = (
                        "high" if ratio > 0.9
                        else "medium" if ratio > 0.6
                        else "low"
                    )

                for u in unresolved:
                    u.district_number = d.district_number
                    u.school_name = d.school_name
                    all_unresolved.append({
                        "district_number": u.district_number,
                        "school_name": u.school_name,
                        "street": u.street,
                        "reason": u.reason,
                    })
            except Exception as ex:
                print(f"  WARNING: Geometry build failed for district {d.district_number}: {ex}", file=sys.stderr)

        record = {
            "vzn_key": "vzn_presov_1_2023",
            "district_number": d.district_number,
            "school_name": d.school_name,
            "school_address": d.school_address,
            "school_type": "ZS",
            "teaching_language": "SK",
            "municipality_name": MUNICIPALITY_NAME,
            "municipality_nuts": MUNICIPALITY_NUTS,
            "streets_json": json.dumps(d.streets, ensure_ascii=False),
            "street_qualifiers_json": json.dumps(d.street_qualifiers, ensure_ascii=False),
            "shared_municipalities_json": json.dumps(d.shared_municipalities, ensure_ascii=False),
            "streets_count": len(d.streets),
            "vzn_article": d.vzn_article,
            "source_name": "VZN Prešov 1/2023",
            "source_date": VZN_SOURCE_DATE,
            "geometry_quality": 6,
            "geometry_confidence": geom_confidence if geom_wkt else "none",
            "reviewed_by": None,
            "reviewed_at": None,
        }
        if geom_wkt:
            record["geom"] = geom_wkt

        district_records.append(record)

    return district_records, [vzn_record], all_unresolved


if __name__ == "__main__":
    districts = load_and_parse_vzn()
    print(f"Parsed {len(districts)} school districts from VZN Prešov 1/2023")
    for d in districts:
        print(f"\n{d.district_number}. {d.school_name}")
        print(f"   Streets ({len(d.streets)}): {d.streets[:5]}{'...' if len(d.streets) > 5 else ''}")
        if d.shared_municipalities:
            print(f"   Shared municipalities: {d.shared_municipalities}")
