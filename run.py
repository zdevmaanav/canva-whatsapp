"""
run.py  --  MAIN LAUNCHER (this is the only file you run)
=========================================================

Just type:   python run.py

It walks you through everything with a menu. You never edit any code.

Menu:
  1. Set up / edit my account details   (do this first, once)
  2. Test my connections                 (checks Google + Gupshup work)
  3. Run a batch                         (the actual send)
  4. Exit
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from config_manager import load_client, create_or_edit_client, list_clients


LINE = "=" * 58


def header(t):
    print("\n" + LINE)
    print(f"  {t}")
    print(LINE)


def pause(msg="Press Enter to continue..."):
    input(f"\n{msg}")


# ---------------------------------------------------------------
def menu_setup():
    header("SET UP MY ACCOUNT")
    print("""
This saves your details so you don't re-enter them each time.
Have these ready:
  - Your Google Sheet link
  - The folder on this PC where your images are
  - Your Google service-account file (the .json you were given)
  - Your Canva template link
  - Your Gupshup: API key, sender number, app name, template ID
  - Your image host link (Supabase or a public folder URL)

If you don't have some of these yet, ask your provider.
""")
    create_or_edit_client()


# ---------------------------------------------------------------
def menu_test():
    header("TEST MY CONNECTIONS")
    cfg = load_client()
    ok = True

    # --- Google Sheet ---
    print("\n[1/2] Checking Google Sheet access...")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            cfg["service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(cfg["sheet_id"])
        ws = sh.worksheet(cfg["sheet_tab"])
        rows = ws.get_all_records()
        print(f"      OK - sheet opened, {len(rows)} rows found.")
        # check columns exist
        if rows:
            missing = [c for c in (cfg["image_col"], cfg["number_col"]) if c not in rows[0]]
            if missing:
                print(f"      ! Column(s) not found in sheet: {missing}")
                print(f"        Your sheet headers are: {list(rows[0].keys())}")
                ok = False
    except FileNotFoundError:
        print(f"      FAILED - service-account file not found:\n        {cfg['service_account']}")
        ok = False
    except Exception as e:
        msg = str(e)
        if "PermissionError" in msg or "403" in msg:
            print("      FAILED - the sheet isn't shared with your service account.")
            print("        Open the sheet -> Share -> add the service-account email as Viewer.")
        else:
            print(f"      FAILED - {msg[:200]}")
        ok = False

    # --- Gupshup ---
    print("\n[2/2] Checking Gupshup...")
    try:
        import requests
        # lightweight check: app/template presence via a harmless call
        r = requests.get(
            "https://api.gupshup.io/wa/app",
            headers={"apikey": cfg["gupshup_api_key"]},
            timeout=30,
        )
        if r.status_code in (200, 201):
            print("      OK - Gupshup API key accepted.")
        elif r.status_code in (401, 403):
            print("      FAILED - Gupshup API key rejected. Check the key.")
            ok = False
        else:
            print(f"      (Gupshup responded {r.status_code}; key likely fine, send will confirm.)")
    except Exception as e:
        print(f"      Could not reach Gupshup ({str(e)[:120]}). Check internet.")
        ok = False

    print("\n" + ("All good - you're ready to run a batch." if ok
                  else "Some checks failed. Fix the above, then test again."))


# ---------------------------------------------------------------
def menu_run():
    header("RUN A BATCH")
    cfg = load_client()
    client = cfg["client_name"]

    # STAGE 1 -------------------------------------------------
    print("\n--- Step 1 of 3: reading your sheet & preparing images ---")
    import stage1_build
    try:
        stage1_build.build(cfg)
    except Exception as e:
        print(f"\nStopped: {str(e)[:300]}")
        print("Fix the issue (often: sheet not shared, or wrong folder path) and try again.")
        return

    base = os.path.join(HERE, "work", client)
    xlsx = os.path.join(base, f"{client}_bulk.xlsx")
    if not os.path.exists(xlsx):
        print("No data file was produced (no valid rows?). Stopping.")
        return

    # STAGE 1.5 -----------------------------------------------
    print("\n--- Step 2 of 3: filling your Canva template ---")
    print("""
This opens Canva in a browser and fills your template automatically.
If the automatic step can't find a button (Canva sometimes changes its
layout), it will PAUSE and tell you exactly which few clicks to do by
hand - then you press Enter and it continues. You won't get stuck.
""")
    choice = input("Run Canva automatically? (Y = auto / m = I'll do Canva myself): ").strip().lower()

    if choice == "m":
        _manual_canva_instructions(cfg, base)
    else:
        session = os.path.join(base, "canva_session.json")
        if not os.path.exists(session):
            print("\nFirst time: you need to log into Canva once.")
            print("A browser will open - log in, then come back and press Enter.")
            pause("Press Enter to open the Canva login...")
            import stage1_5_canva
            stage1_5_canva.do_login(cfg)
        try:
            import stage1_5_canva
            stage1_5_canva.run(cfg)
        except Exception as e:
            print(f"\nAuto-Canva hit a problem: {str(e)[:200]}")
            print("Switching to manual mode so you're not stuck.")
            _manual_canva_instructions(cfg, base)

    # confirm PDF exists
    export_dir = os.path.join(base, "export")
    pdfs = [f for f in os.listdir(export_dir) if f.lower().endswith(".pdf")] if os.path.exists(export_dir) else []
    if not pdfs:
        print(f"\nNo exported PDF found in:\n  {export_dir}")
        print("Put the exported Canva PDF there, then choose 'Run a batch' again")
        print("- it will skip ahead to sending.")
        return

    # STAGE 2 -------------------------------------------------
    print("\n--- Step 3 of 3: sending on WhatsApp ---")
    confirm = input(f"Ready to send to all numbers in the sheet? (yes/no): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Not sending. Your PDF is saved; run again when ready.")
        return
    import stage2_send
    try:
        stage2_send.run(cfg)
    except Exception as e:
        print(f"\nSending stopped: {str(e)[:300]}")
        return
    print("\nBatch complete. Check the send log in your work folder for details.")


def _manual_canva_instructions(cfg, base):
    print("\n" + "-" * 50)
    print("DO THESE STEPS IN CANVA:")
    print("-" * 50)
    print(f"  1. Open your template:\n     {cfg.get('canva_template_url','(your template link)')}")
    print(f"  2. Apps -> Bulk Create -> Upload data")
    print(f"  3. Choose this file:\n     {os.path.join(base, cfg['client_name'] + '_bulk.xlsx')}")
    print(f"  4. Connect the Image field to your photo frame")
    print(f"  5. Generate the designs")
    print(f"  6. Share -> Download -> PDF Standard (whole batch as ONE PDF)")
    print(f"  7. Save that PDF into this folder:\n     {os.path.join(base,'export')}")
    print("-" * 50)
    pause("Do those steps, then press Enter here to continue to sending...")


# ---------------------------------------------------------------
def main():
    header("Canva -> WhatsApp Sender")
    if not list_clients():
        print("\nLooks like your first time. Let's set up your account.")
        menu_setup()

    while True:
        print("""
What do you want to do?
  1. Set up / edit my account details
  2. Test my connections
  3. Run a batch
  4. Exit
""")
        c = input("Choose 1-4: ").strip()
        if c == "1":
            menu_setup()
        elif c == "2":
            menu_test()
        elif c == "3":
            menu_run()
        elif c == "4":
            print("Bye.")
            break
        else:
            print("Please type 1, 2, 3, or 4.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
