"""Tighter legible captures: zoom the map onto the MRK exclusion (Nešpora) and
the overcrowding pin (Šmeralova) after triggering each finding, then screenshot
the map region only."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:3210"
CHROME = "/usr/bin/google-chrome-stable"
DOCS = "/home/node/.openclaw/workspace/projects/skolske-obvody-44/docs"
VP = {"width": 1440, "height": 960}


def drill(page):
    purple = page.locator(".leaflet-overlay-pane svg path[stroke='#7c3aed']")
    purple.first.wait_for(timeout=15000)
    purple.first.click(force=True)
    page.wait_for_timeout(2500)


def map_clip(page):
    box = page.locator(".leaflet-container").first.bounding_box()
    return {"x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"]}


def run():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
        page = b.new_page(viewport=VP)
        page.goto(f"{BASE}/map", wait_until="domcontentloaded")
        page.wait_for_selector(".leaflet-container", timeout=20000)
        page.wait_for_timeout(1500)
        drill(page)
        page.wait_for_timeout(1500)

        # P-e: click finding, then zoom map in twice toward Nešpora to make the
        # exclusion dots + annotation legible.
        page.locator("button", has_text="takmer celý").first.click()
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{DOCS}/verify-pe-mrk-exclusion-zoom.png", clip=map_clip(page))
        print("shot verify-pe-mrk-exclusion-zoom.png")

        # P-f: click overcrowding finding; the map flies to Šmeralova centroid.
        page.locator("button", has_text="712 prekračuje kapacitu").first.click()
        page.wait_for_timeout(2500)
        # Zoom in toward the school pin for a legible badge.
        page.mouse.move(720, 480)
        for _ in range(2):
            page.mouse.wheel(0, -300)
            page.wait_for_timeout(800)
        page.wait_for_timeout(1200)
        page.screenshot(path=f"{DOCS}/verify-pf-overcrowding-zoom.png", clip=map_clip(page))
        print("shot verify-pf-overcrowding-zoom.png")
        b.close()
        return 0


if __name__ == "__main__":
    sys.exit(run())
