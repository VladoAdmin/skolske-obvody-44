"""
Browser verification for feat/demo-mode Tasks 2 & 3:
  * Task 2 — P-e MRK exclusion layer on Mirka Nešpora č. 2
  * Task 3 — P-f overcrowding viz on Šmeralova č. 25
Drives real Chrome via Playwright, captures BEFORE/AFTER screenshots, exercises
the finding-click -> map-focus flow, and reports console errors.
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3210"
CHROME = "/usr/bin/google-chrome-stable"
DOCS = "/home/node/.openclaw/workspace/projects/skolske-obvody-44/docs"
VP = {"width": 1440, "height": 960}

console_errors = []


def shoot(page, name):
    path = f"{DOCS}/{name}.png"
    page.screenshot(path=path)
    print(f"  [shot] {path}")


def drill_into_psk(page):
    purple = page.locator(".leaflet-overlay-pane svg path[stroke='#7c3aed']")
    purple.first.wait_for(timeout=15000)
    purple.first.click(force=True)
    page.wait_for_timeout(2500)
    labels = page.locator(".leaflet-control-layers-overlays label").all_inner_texts()
    return any("Obvody" in l for l in labels)


def click_district_polygon(page, contains_text):
    """Click a district polygon by hovering to find the one whose tooltip
    matches, then click it. Simpler: dispatch the app's select event via the
    findings panel instead (done separately). Here we click by polygon path
    using its bound tooltip is unreliable, so we click via the findings list."""
    pass


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME, headless=True, args=["--no-sandbox"]
        )
        page = browser.new_page(viewport=VP)
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(f"PAGEERROR {e}"))

        page.goto(f"{BASE}/map", wait_until="domcontentloaded")
        page.wait_for_selector(".leaflet-container", timeout=20000)
        page.wait_for_timeout(1500)

        if not drill_into_psk(page):
            print("FAIL: could not drill into PSK")
            browser.close()
            return 1
        page.wait_for_timeout(1500)

        # BEFORE: clean PSK map, no finding selected.
        shoot(page, "verify-pe-pf-BEFORE-clean-map")

        # --- Task 2: click the P-e segregation finding in the findings list ---
        # The findings list lives in the side panel. Find the button whose text
        # mentions the Mirka Nešpora segregation signal.
        pe_btn = page.locator("button", has_text="takmer celý")
        if pe_btn.count() == 0:
            # fallback: any button mentioning the district + segregation
            pe_btn = page.locator("button", has_text="Mirka Nešpora")
        print(f"  P-e finding buttons matched: {pe_btn.count()}")
        pe_btn.first.scroll_into_view_if_needed()
        pe_btn.first.click()
        page.wait_for_timeout(3000)
        # The MRK exclusion legend should appear.
        legend = page.locator(".demo-finding-legend")
        has_legend = legend.count() > 0
        legend_txt = legend.first.inner_text() if has_legend else ""
        mrk_label = page.locator(".demo-mrk-exclusion-label")
        print(f"  legend present: {has_legend}; MRK exclusion labels: {mrk_label.count()}")
        print(f"  legend text: {legend_txt!r}")
        shoot(page, "verify-pe-AFTER-mrk-exclusion")

        pe_ok = has_legend and "MRK" in legend_txt and mrk_label.count() > 0

        # --- Task 3: click the P-f overcrowding finding (Šmeralova 712/560) ---
        pf_btn = page.locator("button", has_text="712 prekračuje kapacitu")
        print(f"  P-f finding buttons matched: {pf_btn.count()}")
        if pf_btn.count() > 0:
            pf_btn.first.scroll_into_view_if_needed()
            pf_btn.first.click()
            page.wait_for_timeout(3000)
        legend2 = page.locator(".demo-finding-legend")
        legend2_txt = legend2.first.inner_text() if legend2.count() > 0 else ""
        oc_label = page.locator(".demo-overcrowd-label")
        print(f"  overcrowd labels: {oc_label.count()}")
        print(f"  legend2 text: {legend2_txt!r}")
        shoot(page, "verify-pf-AFTER-overcrowding")

        pf_ok = oc_label.count() > 0 and "preplnené" in legend2_txt

        browser.close()

        print("\n=== RESULT ===")
        print(f"  Task 2 (P-e MRK exclusion): {'PASS' if pe_ok else 'FAIL'}")
        print(f"  Task 3 (P-f overcrowding):  {'PASS' if pf_ok else 'FAIL'}")
        print(f"  console errors ({len(console_errors)}):")
        for e in console_errors[:15]:
            print(f"    - {e}")
        return 0 if (pe_ok and pf_ok and not console_errors) else 2


if __name__ == "__main__":
    sys.exit(run())
