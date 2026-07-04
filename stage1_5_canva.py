"""
stage1_5_canva.py
-----------------
STAGE 1.5 (browser automation, FRAGILE by nature).

Drives a real Chrome via Playwright to:
  1. open the client's Canva template
  2. run Bulk Create with the xlsx built in Stage 1
  3. bind the image field
  4. generate the pages
  5. export the whole batch as a PDF into work/<client>/export/

IMPORTANT — read this before relying on it:
  * Canva's UI changes will break the selectors below. When that happens the
    script pauses on a step and screenshots to work/<client>/debug/. Update the
    selector for that step. This is expected maintenance, not a bug.
  * Run the ONE-TIME login first (saves a session per client), then normal runs
    reuse that session.

One-time login (per client), opens a visible browser for you to log in:
    python stage1_5_canva.py --login

Normal run:
    python stage1_5_canva.py

Flags:
    --login      just log in and save the session, then exit
    --headful    show the browser during a normal run (default is visible anyway
                 for this tool, because Bulk Create is finicky headless)
    --slow 200   add 200ms between actions (helps on slow machines)
"""

import os
import sys
import time
import argparse

from config_manager import load_client

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit("Playwright not installed. Run:\n  pip install playwright\n  python -m playwright install chromium")


def paths_for(client):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", client)
    return {
        "base": base,
        "xlsx": os.path.join(base, f"{client}_bulk.xlsx"),
        "export": os.path.join(base, "export"),
        "debug": os.path.join(base, "debug"),
        "session": os.path.join(base, "canva_session.json"),
    }


def shot(page, debug_dir, name):
    os.makedirs(debug_dir, exist_ok=True)
    p = os.path.join(debug_dir, f"{name}_{int(time.time())}.png")
    try:
        page.screenshot(path=p, full_page=True)
        print(f"    [screenshot] {p}")
    except Exception:
        pass


def do_login(cfg):
    """One-time: open visible browser, let user log in, save storage state."""
    P = paths_for(cfg["client_name"])
    os.makedirs(P["base"], exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto("https://www.canva.com/login")
        print("\n>>> A browser window opened.")
        print(">>> Log into THIS client's Canva account fully.")
        print(">>> When you can see your Canva home/dashboard, come back here.")
        input(">>> Press Enter once you're logged in... ")
        ctx.storage_state(path=P["session"])
        print(f"Session saved: {P['session']}")
        browser.close()


def try_click(page, selectors, debug_dir, step, timeout=15000):
    """Try a list of candidate selectors; click the first that appears."""
    last_err = None
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout, state="visible")
            el.click()
            return True
        except PWTimeout as e:
            last_err = e
            continue
    shot(page, debug_dir, f"fail_{step}")
    print(f"    ! step '{step}': none of the selectors matched.")
    print(f"      tried: {selectors}")
    print(f"      A screenshot was saved to work/<client>/debug/. Update the selector.")
    return False


def run(cfg, slow_mo=0):
    client = cfg["client_name"]
    P = paths_for(client)
    os.makedirs(P["export"], exist_ok=True)

    if not os.path.exists(P["xlsx"]):
        raise SystemExit(f"xlsx not found: {P['xlsx']}\nRun stage1_build.py first.")
    if not os.path.exists(P["session"]):
        raise SystemExit("No saved Canva session. Run:\n  python stage1_5_canva.py --login")

    template_url = cfg.get("canva_template_url", "").strip()
    if not template_url:
        raise SystemExit("canva_template_url is empty in this client's config.")

    print(f"\n[Stage 1.5] Client: {client}")
    print("  Launching browser (visible; Bulk Create is unreliable headless)...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=slow_mo)
        ctx = browser.new_context(
            storage_state=P["session"],
            accept_downloads=True,
        )
        page = ctx.new_page()

        # ---- open the template ----
        print("  Opening template...")
        page.goto(template_url, wait_until="load")
        page.wait_for_timeout(6000)  # editor is heavy; give it time
        shot(page, P["debug"], "01_template_open")

        # ---- open Bulk Create app ----
        # Canva flow: Apps (left rail) -> search "Bulk Create" -> open.
        # Selectors below are best-effort with fallbacks. EXPECT to adjust these.
        print("  Opening Bulk Create...  (if this stalls, check debug screenshots)")

        # open the Apps / left panel
        try_click(page, [
            'button[aria-label="Apps"]',
            'div[aria-label="Apps"]',
            'text=Apps',
        ], P["debug"], "open_apps", timeout=20000)
        page.wait_for_timeout(2000)

        # search Bulk Create
        try:
            search = page.wait_for_selector('input[placeholder*="Search"]', timeout=10000)
            search.fill("Bulk Create")
            page.wait_for_timeout(2500)
        except PWTimeout:
            shot(page, P["debug"], "fail_search_apps")
            print("    ! couldn't find Apps search box. Adjust selector.")

        try_click(page, [
            'text=Bulk Create',
            'div[aria-label*="Bulk Create"]',
        ], P["debug"], "open_bulk_create", timeout=15000)
        page.wait_for_timeout(3000)
        shot(page, P["debug"], "02_bulk_create_panel")

        # ---- upload the xlsx ----
        # Bulk Create -> "Upload data" -> file chooser
        print("  Uploading data file...")
        try:
            with page.expect_file_chooser(timeout=20000) as fc_info:
                try_click(page, [
                    'text=Upload data',
                    'text=Upload CSV or XLSX',
                    'button:has-text("Upload")',
                ], P["debug"], "click_upload_data", timeout=15000)
            fc = fc_info.value
            fc.set_files(P["xlsx"])
            print("    file chosen.")
        except PWTimeout:
            shot(page, P["debug"], "fail_file_chooser")
            print("    ! file chooser never appeared. Adjust the 'Upload data' selector.")
            browser.close()
            return
        page.wait_for_timeout(5000)
        shot(page, P["debug"], "03_data_uploaded")

        # ---- connect the Image field to the frame ----
        # This is the least stable step: you drag the "Image" data field onto the
        # photo frame, OR right-click the frame -> Connect data -> Image.
        # UI-dependent; we pause for manual binding if auto fails.
        print("  Binding image field...")
        bound = try_click(page, [
            'text=Connect data',
            'text=Image',
        ], P["debug"], "bind_image", timeout=8000)
        if not bound:
            shot(page, P["debug"], "04_bind_manual_needed")
            print("\n    >>> Auto-bind failed (this step is very UI-specific).")
            print("    >>> In the open browser: connect the 'Image' data field to your")
            print("    >>> photo frame manually (right-click frame -> Connect data -> Image).")
            input("    >>> Press Enter here once the image is bound... ")

        # ---- generate ----
        print("  Generating pages...")
        try_click(page, [
            'button:has-text("Continue")',
            'button:has-text("Generate")',
            'text=Generate designs',
        ], P["debug"], "generate", timeout=15000)
        # generation can take a while for 100 rows
        page.wait_for_timeout(15000)
        shot(page, P["debug"], "05_generated")

        # ---- export as PDF ----
        print("  Exporting as PDF...")
        try_click(page, [
            'button[aria-label="Share"]',
            'text=Share',
        ], P["debug"], "open_share", timeout=15000)
        page.wait_for_timeout(1500)
        try_click(page, [
            'text=Download',
        ], P["debug"], "open_download", timeout=10000)
        page.wait_for_timeout(1500)

        # choose PDF file type
        try_click(page, [
            'text=PDF Standard',
            'text=PDF Print',
            'div[aria-label*="File type"]',
        ], P["debug"], "choose_pdf", timeout=10000)
        page.wait_for_timeout(1000)

        # final download button -> capture the file
        try:
            with page.expect_download(timeout=120000) as dl_info:
                try_click(page, [
                    'button:has-text("Download")',
                    'text=Download',
                ], P["debug"], "final_download", timeout=15000)
            download = dl_info.value
            out_pdf = os.path.join(P["export"], f"{client}_batch.pdf")
            download.save_as(out_pdf)
            print(f"\n[Stage 1.5 done] PDF saved: {out_pdf}")
            print("  Next: python stage2_send.py")
        except PWTimeout:
            shot(page, P["debug"], "fail_download")
            print("    ! download didn't start. Check debug screenshots; finish export")
            print("      manually into work/<client>/export/ and run stage2_send.py.")

        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true", help="one-time: log in and save session")
    ap.add_argument("--slow", type=int, default=0, help="ms delay between actions")
    args = ap.parse_args()

    cfg = load_client()
    if args.login:
        do_login(cfg)
    else:
        run(cfg, slow_mo=args.slow)
