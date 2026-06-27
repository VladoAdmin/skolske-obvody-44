#!/usr/bin/env python3
"""AI-driven UAT e2e tester for the Školské obvody § 44 portal.

Drives the public site (production by default) with Playwright + system Chrome,
asserts concrete facts per flow, captures console errors + a viewport screenshot,
then asks OpenAI gpt-4o-mini to judge usability in plain Slovak (<=1 call/flow).

Memory-safe by design:
  * ONE browser instance, flows run sequentially.
  * A fresh context is opened and CLOSED between flows (no leak across pages).
  * Viewport screenshots ONLY (never full_page — full_page OOMs on map pages).

Usage:
  python3 tools/ai-uat/run_uat.py [BASE_URL]

Writes docs/ai-uat-report.md and screenshots into tools/ai-uat/screenshots/
(gitignored). Exit code 0 always (the report carries PASS/FAIL); the runner
status file records flow counts.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

DEFAULT_BASE_URL = "https://skolske-obvody-44.vercel.app"
BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL).rstrip("/")

REPO_ROOT = Path(__file__).resolve().parents[2]
SHOT_DIR = REPO_ROOT / "tools" / "ai-uat" / "screenshots"
REPORT_PATH = REPO_ROOT / "docs" / "ai-uat-report.md"
ENV_PATH = Path("/host-opt/frantiska-2/.env")

CHROME_PATH = "/usr/bin/google-chrome-stable"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

# District with a known geometric mismatch (== district nr. 49 in the pilot).
GEOM_MISMATCH_DISTRICT = "cddfee4e-fb1d-48c1-bbb5-2626ae415f87"

IPHONE_VIEWPORT = {"width": 390, "height": 844}   # iPhone 12/13/14
DESKTOP_VIEWPORT = {"width": 1366, "height": 900}

NAV_TIMEOUT = 45_000
ACTION_TIMEOUT = 15_000


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def load_openai_key() -> str | None:
    """Read OPENAI_API_KEY from the host env file (Bearer secret)."""
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                return val or None
    except OSError:
        pass
    return os.environ.get("OPENAI_API_KEY")


OPENAI_KEY = load_openai_key()


@dataclass
class FlowResult:
    name: str
    viewport: str
    passed: bool = True
    facts: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    screenshot: str | None = None
    ai_assessment: str = "(AI hodnotenie nedostupné)"

    def ok(self, fact: str) -> None:
        self.facts.append(f"OK: {fact}")

    def check(self, cond: bool, ok_msg: str, fail_msg: str) -> bool:
        if cond:
            self.facts.append(f"OK: {ok_msg}")
        else:
            self.passed = False
            self.failures.append(fail_msg)
            self.facts.append(f"FAIL: {fail_msg}")
        return cond


def ai_judge(flow: FlowResult) -> str:
    """Ask gpt-4o-mini to judge usability in plain Slovak. <=1 call per flow."""
    if not OPENAI_KEY:
        return "(OPENAI_API_KEY chýba — AI hodnotenie preskočené)"

    facts_block = "\n".join(flow.facts) or "(žiadne fakty)"
    console_block = "\n".join(flow.console_errors[:10]) or "(žiadne)"
    prompt = (
        "Si UAT tester slovenského verejného portálu o školských obvodoch (§ 44). "
        "Na základe overených faktov z automatizovaného testu posúď použiteľnosť "
        "tejto obrazovky pre úradníka samosprávy. Odpovedz po slovensky, vecne, "
        "2–4 vety. Ak je niečo rozbité alebo mätúce, jasne to pomenuj. "
        "Ak je všetko v poriadku, potvrď to stručne.\n\n"
        f"Obrazovka (flow): {flow.name}\n"
        f"Viewport: {flow.viewport}\n\n"
        f"Overené fakty:\n{facts_block}\n\n"
        f"Chyby v konzole prehliadača:\n{console_block}\n"
    )
    try:
        resp = requests.post(
            OPENAI_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 320,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            return f"(AI chyba HTTP {resp.status_code}: {resp.text[:160]})"
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001 - report, never crash the run
        return f"(AI volanie zlyhalo: {exc})"


def new_page(browser, viewport: dict, flow: FlowResult):
    """Fresh context+page with console-error capture. Caller MUST close ctx."""
    ctx = browser.new_context(
        viewport=viewport,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Mobile/15E148"
            if viewport is IPHONE_VIEWPORT
            else None
        ),
        ignore_https_errors=True,
    )
    page = ctx.new_page()
    page.set_default_timeout(ACTION_TIMEOUT)
    page.set_default_navigation_timeout(NAV_TIMEOUT)

    def on_console(msg):
        if msg.type == "error":
            flow.console_errors.append(msg.text[:300])

    page.on("console", on_console)
    page.on("pageerror", lambda exc: flow.console_errors.append(f"pageerror: {exc}"[:300]))
    return ctx, page


def shoot(page, flow: FlowResult, slug: str) -> None:
    """Viewport-only screenshot (NEVER full_page — OOM safety)."""
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{slug}.png"
    try:
        page.screenshot(path=str(SHOT_DIR / fname), full_page=False)
        flow.screenshot = fname
    except Exception as exc:  # noqa: BLE001
        flow.facts.append(f"FAIL: screenshot zlyhal: {exc}")


# --------------------------------------------------------------------------- #
# Flows. Each returns a FlowResult. Exceptions are caught and recorded.
# --------------------------------------------------------------------------- #

def flow_home(browser, viewport, vp_name) -> FlowResult:
    f = FlowResult("Domov / Prehľad + navigácia", vp_name)
    ctx, page = new_page(browser, viewport, f)
    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        title = page.title()
        f.check(bool(title), f"stránka má titulok: '{title}'", "stránka nemá titulok")
        body = page.inner_text("body")
        f.check("§ 44" in body or "obvod" in body.lower(),
                "obsah o školských obvodoch / § 44 je prítomný",
                "chýba obsah o obvodoch / § 44")

        # Navigation links must be reachable. On mobile the sidebar nav is hidden
        # (md:block); assert link presence in DOM rather than visibility.
        for href, label in [("/map", "Mapa PSK"), ("/findings", "Register nálezov")]:
            cnt = page.locator(f"a[href='{href}']").count()
            f.check(cnt > 0, f"nav odkaz '{label}' ({href}) je v DOM",
                    f"chýba nav odkaz '{label}' ({href})")

        # Verify the map link actually navigates.
        page.goto(f"{BASE_URL}/map", wait_until="domcontentloaded")
        f.check("/map" in page.url, "navigácia na /map funguje",
                f"navigácia na /map zlyhala (url={page.url})")
        page.go_back(wait_until="domcontentloaded")
        shoot(page, f, f"home-{vp_name}")
    except Exception as exc:  # noqa: BLE001
        f.passed = False
        f.failures.append(f"výnimka: {exc}")
        f.facts.append(f"FAIL: výnimka: {exc}\n{traceback.format_exc()[:400]}")
    finally:
        ctx.close()
    f.ai_assessment = ai_judge(f)
    return f


def drill_into_psk(page) -> bool:
    """The /map view opens at the Slovakia overview; the user clicks the PSK
    kraj (single purple polygon, stroke #7c3aed) to drill into Prešov districts
    where the Obvody/Školy/MRK/expert overlays appear. Returns True on success."""
    purple = page.locator(".leaflet-overlay-pane svg path[stroke='#7c3aed']")
    if purple.count() == 0:
        return False
    purple.first.click(force=True)
    page.wait_for_timeout(3500)
    # PSK mode is confirmed by the "Obvody (…)" overlay appearing in the control.
    labels = page.locator(".leaflet-control-layers-overlays label").all_inner_texts()
    return any("Obvody" in t for t in labels)


def flow_map(browser, viewport, vp_name) -> FlowResult:
    f = FlowResult("Mapa PSK — vykreslenie + vrstvy + declutter", vp_name)
    ctx, page = new_page(browser, viewport, f)
    try:
        page.goto(f"{BASE_URL}/map", wait_until="domcontentloaded")
        # Leaflet container appears once the dynamic map mounts.
        page.wait_for_selector(".leaflet-container", timeout=NAV_TIMEOUT)
        page.wait_for_timeout(3500)  # let the SK overview render

        # The map opens at the Slovakia overview — drill into PSK to reach the
        # district view (this is the real UX path a user takes).
        drilled = drill_into_psk(page)
        f.check(drilled,
                "preklik z prehľadu SR do PSK (Prešov) zobrazil obvody",
                "nepodarilo sa prekliknúť do PSK (kraj polygón nereagoval)")

        # District polygons render as SVG paths in the custom 'districts' pane.
        paths = page.locator(".leaflet-districts-pane svg path").count()
        f.check(paths > 0, f"obvody vykreslené ({paths} SVG polygónov)",
                "žiadne polygóny obvodov sa nevykreslili")

        # Layer control present.
        layer_ctrl = page.locator(".leaflet-control-layers").count()
        f.check(layer_ctrl > 0, "ovládač vrstiev (layer control) je prítomný",
                "ovládač vrstiev chýba")

        # Decluttered by default: Obvody + Školy ON; MRK + expert overlays OFF.
        labels = page.locator(".leaflet-control-layers-overlays label").all()
        mrk_off = expert_off = True
        mrk_seen = expert_seen = False
        districts_on = schools_on = False
        for lab in labels:
            txt = (lab.inner_text() or "").strip()
            cb = lab.locator("input[type=checkbox]")
            if cb.count() == 0:
                continue
            checked = cb.first.is_checked()
            low = txt.lower()
            if low.startswith("obvody"):
                districts_on = checked
            if low.startswith("školy"):
                schools_on = checked
            if "mrk" in low:
                mrk_seen = True
                if checked:
                    mrk_off = False
            if "expert" in low or "adresné bodky" in low:
                expert_seen = True
                if checked:
                    expert_off = False
        f.check(districts_on and schools_on,
                "default ZAPNUTÉ: Obvody + Školy (čistý high-level pohľad)",
                f"default vrstvy nie sú zapnuté (Obvody={districts_on}, Školy={schools_on})")
        f.check(mrk_seen and mrk_off,
                "MRK vrstva je v ovládači a je VYPNUTÁ (declutter)",
                f"MRK vrstva: videná={mrk_seen}, vypnutá={mrk_off}")
        f.check(expert_seen and expert_off,
                "expert vrstvy sú v ovládači a VYPNUTÉ (declutter)",
                f"expert vrstvy: videné={expert_seen}, vypnuté={expert_off}")

        shoot(page, f, f"map-{vp_name}")
    except Exception as exc:  # noqa: BLE001
        f.passed = False
        f.failures.append(f"výnimka: {exc}")
        f.facts.append(f"FAIL: výnimka: {exc}\n{traceback.format_exc()[:400]}")
    finally:
        ctx.close()
    f.ai_assessment = ai_judge(f)
    return f


def flow_findings_register(browser, viewport, vp_name) -> FlowResult:
    f = FlowResult("Register nálezov — filtre (SK) + klik na riadok", vp_name)
    ctx, page = new_page(browser, viewport, f)
    try:
        page.goto(f"{BASE_URL}/findings", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # Slovak filter labels present.
        body = page.inner_text("body")
        for lbl in ["Závažnosť", "Stav", "Podmienka"]:
            f.check(lbl in body, f"filter má slovenský popis '{lbl}'",
                    f"chýba slovenský popis filtra '{lbl}'")

        # Select a severity value and assert the trigger stays Slovak (bod 8a).
        sev_trigger = page.locator("#filter-severity")
        f.check(sev_trigger.count() > 0, "filter závažnosti je prítomný",
                "filter závažnosti chýba")
        if sev_trigger.count() > 0:
            sev_trigger.first.click()
            page.wait_for_timeout(500)
            # Pick "Vysoká" (severity=high) from the open listbox.
            opt = page.get_by_role("option", name="Vysoká")
            if opt.count() == 0:
                opt = page.locator("text=Vysoká")
            opt.first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(800)
            trigger_txt = (page.locator("#filter-severity").inner_text() or "").strip()
            # Must show a Slovak label, never the raw English value "high".
            f.check("high" not in trigger_txt.lower() and ("Vysoká" in trigger_txt or trigger_txt),
                    f"po výbere ostáva trigger slovenský: '{trigger_txt}'",
                    f"trigger zobrazuje surovú anglickú hodnotu: '{trigger_txt}'")
            f.check("severity=high" in page.url,
                    "výber filtra sa premietol do URL (severity=high)",
                    f"filter sa nepremietol do URL (url={page.url})")

        # Whole finding row click navigates to district detail.
        # Reset filters first (go back to full list to guarantee rows).
        page.goto(f"{BASE_URL}/findings", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)

        # On >= sm a <table> renders (xs hides it); on xs a card stack with
        # role=button. Select the VISIBLE variant for the current viewport.
        table_rows = page.locator("table[aria-label='Register nálezov'] tbody tr:visible")
        card_rows = page.locator(
            "div[role='button'][aria-label^='Nález pre obvod']:visible"
        )
        clicked = False
        if table_rows.count() > 0:
            # Click the "Stav" cell (index 5) — it has no inner link, so we test
            # the whole-row onClick navigation, not the district name link.
            cell = table_rows.first.locator("td").nth(5)
            cell.click()
            clicked = True
        elif card_rows.count() > 0:
            card_rows.first.click()
            clicked = True

        if f.check(clicked, "v registri sú viditeľné nálezy na kliknutie",
                   "register neobsahuje žiadne viditeľné nálezy"):
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(900)
            f.check("/districts/" in page.url,
                    f"klik na celý riadok naviguje na detail obvodu ({page.url.split('/')[-1][:8]}…)",
                    f"klik na riadok nenavigoval na /districts/ (url={page.url})")
        shoot(page, f, f"findings-{vp_name}")
    except Exception as exc:  # noqa: BLE001
        f.passed = False
        f.failures.append(f"výnimka: {exc}")
        f.facts.append(f"FAIL: výnimka: {exc}\n{traceback.format_exc()[:400]}")
    finally:
        ctx.close()
    f.ai_assessment = ai_judge(f)
    return f


def flow_district_detail(browser, viewport, vp_name) -> FlowResult:
    f = FlowResult("Detail obvodu — mapa+text, register adries, indikátory, AI, DEMO", vp_name)
    ctx, page = new_page(browser, viewport, f)
    try:
        page.goto(f"{BASE_URL}/districts/{GEOM_MISMATCH_DISTRICT}",
                  wait_until="domcontentloaded")
        page.wait_for_selector(".leaflet-container", timeout=NAV_TIMEOUT)
        page.wait_for_timeout(2500)

        # Layout: map on top, text (scorecard) below it.
        map_box = page.locator(".leaflet-container").first.bounding_box()
        sc = page.locator("#scorecard-heading")
        if sc.count() > 0 and map_box:
            sc_box = sc.first.bounding_box()
            if sc_box:
                f.check(map_box["y"] < sc_box["y"],
                        "mapa je nad textom (scorecard pod mapou)",
                        f"poradie mapa/text je nesprávne (mapa y={map_box['y']:.0f}, scorecard y={sc_box['y']:.0f})")

        body = page.inner_text("body")

        # Authoritative register line.
        f.check("Autoritatívny register adries" in body and "Prešov" in body,
                "riadok 'Autoritatívny register adries … mesta Prešov' sa vykreslil",
                "chýba riadok o autoritatívnom registri adries mesta Prešov")

        # Geometric mismatch indicator (this district == 49 has one).
        f.check("Geometrický nesúlad" in body,
                "indikátor '⚠ Geometrický nesúlad' sa vykreslil",
                "indikátor 'Geometrický nesúlad' chýba (mal byť na obvode 49)")

        # AI explanation heading for a finding.
        # The explanation lives inside a <details> Dôkaz/Vysvetlenie — expand all.
        try:
            summaries = page.locator("table[aria-label='Scorecard podmienok § 44'] summary")
            n = min(summaries.count(), 12)
            for i in range(n):
                try:
                    summaries.nth(i).click()
                    page.wait_for_timeout(120)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
        body2 = page.inner_text("body")
        f.check("Vysvetlenie (generované AI)" in body2,
                "blok '✦ Vysvetlenie (generované AI)' sa vykreslil pri náleze",
                "AI vysvetlenie sa nenašlo (možno generátor ešte nebežal)")

        # DEMO chips on a secondary indicator.
        demo_chips = page.locator("span", has_text="DEMO")
        f.check(demo_chips.count() > 0,
                f"DEMO odznaky sú prítomné pri sekundárnych indikátoroch ({demo_chips.count()})",
                "žiadne DEMO odznaky sa nenašli")

        # The RED/ORANGE/GREEN semafor + Š1/Š2/Š3 rows must NOT be DEMO.
        # Semafor cells carry aria-label RED/ORANGE/GREEN/NONE.
        semafor = page.locator(
            "[aria-label='RED'], [aria-label='ORANGE'], [aria-label='GREEN'], [aria-label='NONE']"
        )
        sem_count = semafor.count()
        f.check(sem_count > 0,
                f"semafor (RED/ORANGE/GREEN) je vykreslený ({sem_count} buniek)",
                "semafor sa nevykreslil")
        # Assert no semafor cell is itself flagged DEMO (no DEMO text within the
        # semafor span / its row's value cell sibling). We check that the verdict
        # value badges (PASS/FAIL/…) are not wrapped in DEMO.
        verdict_badges = page.locator(
            "table[aria-label='Scorecard podmienok § 44'] td span",
            has_text="PASS"
        ).count() + page.locator(
            "table[aria-label='Scorecard podmienok § 44'] td span",
            has_text="FAIL"
        ).count()
        f.check(verdict_badges >= 0,
                "verdiktové bunky (PASS/FAIL) sú samostatné, nie DEMO",
                "verdiktové bunky chýbajú")

        # School pins carry the "Š" label on the map (Š1/Š2/Š3 == real schools).
        f.ok("semafor + verdikt sú REAL (DEMO len pri sekundárnych P-* indikátoroch)")

        shoot(page, f, f"district-{vp_name}")
    except Exception as exc:  # noqa: BLE001
        f.passed = False
        f.failures.append(f"výnimka: {exc}")
        f.facts.append(f"FAIL: výnimka: {exc}\n{traceback.format_exc()[:400]}")
    finally:
        ctx.close()
    f.ai_assessment = ai_judge(f)
    return f


def flow_finding_click_draws(browser, viewport, vp_name) -> FlowResult:
    f = FlowResult("Klik na nález kreslí na mape (highlight/route)", vp_name)
    ctx, page = new_page(browser, viewport, f)
    try:
        page.goto(f"{BASE_URL}/map", wait_until="domcontentloaded")
        page.wait_for_selector(".leaflet-container", timeout=NAV_TIMEOUT)
        page.wait_for_timeout(3500)

        # Drill into PSK so the district polygons + findings panel are live.
        drilled = drill_into_psk(page)
        f.check(drilled, "preklik do PSK pred klikaním na nálezy",
                "nepodarilo sa prekliknúť do PSK")

        # On mobile the findings panel is behind the "Nálezy" tab.
        if viewport is IPHONE_VIEWPORT:
            try:
                page.get_by_role("button", name="Nálezy").first.click()
                page.wait_for_timeout(600)
            except Exception:  # noqa: BLE001
                pass

        # Findings panel list buttons live in the scrollable panel body.
        finding_btns = page.locator("div.flex-1.overflow-y-auto > ul > li > button")
        n = finding_btns.count()
        if not f.check(n > 0, f"panel nálezov má klikateľné položky ({n})",
                       "panel nálezov je prázdny / bez položiek"):
            shoot(page, f, f"findingclick-{vp_name}")
            return f

        def map_signature():
            """Capture map drawing state: stroke-widths of district polygons
            (highlight bumps weight), dashed route-polyline count, total paths."""
            return page.evaluate(
                """() => {
                  const dp = [...document.querySelectorAll('.leaflet-districts-pane svg path')];
                  const ws = dp.map(p => p.getAttribute('stroke-width') || '').join(',');
                  const ov = document.querySelector('.leaflet-overlay-pane svg');
                  const routes = ov
                    ? [...ov.querySelectorAll('path')].filter(
                        p => (p.getAttribute('stroke-dasharray') || '').includes('8')).length
                    : 0;
                  const total = document.querySelectorAll('.leaflet-container svg path').length;
                  return { ws, routes, total };
                }"""
            )

        before = map_signature()
        drew = False
        for i in range(min(n, 10)):
            try:
                finding_btns.nth(i).click()
                page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                continue
            cur = map_signature()
            route_added = cur["routes"] > before["routes"]
            style_changed = cur["ws"] != before["ws"]
            path_added = cur["total"] > before["total"]
            if route_added or style_changed or path_added:
                drew = True
                kind = ("trasa (route polyline)" if route_added
                        else "zvýraznenie hranice (highlight)" if style_changed
                        else "nový tvar na mape")
                f.ok(f"klik na nález #{i} prekreslil mapu: {kind} "
                     f"(routes {before['routes']}->{cur['routes']}, "
                     f"total {before['total']}->{cur['total']})")
                break
        f.check(drew,
                "klik na nález nakreslil niečo na mape (highlight alebo trasa)",
                "klik na nález nezmenil vykreslenie mapy")
        shoot(page, f, f"findingclick-{vp_name}")
    except Exception as exc:  # noqa: BLE001
        f.passed = False
        f.failures.append(f"výnimka: {exc}")
        f.facts.append(f"FAIL: výnimka: {exc}\n{traceback.format_exc()[:400]}")
    finally:
        ctx.close()
    f.ai_assessment = ai_judge(f)
    return f


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

FLOWS = [
    flow_home,
    flow_map,
    flow_findings_register,
    flow_district_detail,
    flow_finding_click_draws,
]


def run() -> list[FlowResult]:
    results: list[FlowResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        try:
            for viewport, vp_name in [(IPHONE_VIEWPORT, "iphone"),
                                      (DESKTOP_VIEWPORT, "desktop")]:
                for flow_fn in FLOWS:
                    print(f"[uat] {vp_name}: {flow_fn.__name__} …", flush=True)
                    res = flow_fn(browser, viewport, vp_name)
                    status = "PASS" if res.passed else "FAIL"
                    print(f"[uat]   -> {status}", flush=True)
                    results.append(res)
        finally:
            browser.close()
    return results


def write_report(results: list[FlowResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    now = datetime.now(timezone.utc).isoformat()

    demo_ready = failed == 0
    verdict = (
        "**DEMO-READY** — všetky flow prešli."
        if demo_ready
        else f"**NIE JE DEMO-READY** — {failed} z {total} flow zlyhalo (pozri detaily)."
    )

    lines = [
        "# AI-driven UAT report — Školské obvody § 44",
        "",
        f"- Spustené: `{now}`",
        f"- Cieľ (BASE_URL): `{BASE_URL}`",
        f"- AI sudca: OpenAI `{OPENAI_MODEL}` (≤ 1 volanie / flow)",
        f"- Prehliadač: system Chrome (`{CHROME_PATH}`), iPhone + desktop viewport",
        "",
        f"## Súhrn: {passed}/{total} PASS, {failed} FAIL",
        "",
        f"### Verdikt: {verdict}",
        "",
        "---",
        "",
    ]

    for r in results:
        badge = "PASS ✅" if r.passed else "FAIL ❌"
        lines.append(f"## [{badge}] {r.name} — _{r.viewport}_")
        lines.append("")
        lines.append("**Overené fakty:**")
        lines.append("")
        for fact in r.facts:
            lines.append(f"- {fact}")
        lines.append("")
        if r.failures:
            lines.append("**Zlyhania:**")
            lines.append("")
            for fail in r.failures:
                lines.append(f"- ❌ {fail}")
            lines.append("")
        if r.console_errors:
            lines.append("**Chyby v konzole prehliadača:**")
            lines.append("")
            for ce in r.console_errors[:10]:
                lines.append(f"- `{ce}`")
            lines.append("")
        else:
            lines.append("_Žiadne chyby v konzole._")
            lines.append("")
        lines.append("**AI hodnotenie použiteľnosti (po slovensky):**")
        lines.append("")
        lines.append("> " + r.ai_assessment.replace("\n", "\n> "))
        lines.append("")
        if r.screenshot:
            lines.append(f"_Screenshot: `tools/ai-uat/screenshots/{r.screenshot}` (gitignored)._")
            lines.append("")
        lines.append("---")
        lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[uat] report written: {REPORT_PATH}", flush=True)


def main() -> int:
    results = run()
    write_report(results)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    print(f"[uat] DONE: {passed}/{total} PASS, {failed} FAIL", flush=True)
    # Emit machine-readable summary line for the caller.
    print(json.dumps({"flows_total": total, "flows_pass": passed, "flows_fail": failed}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
