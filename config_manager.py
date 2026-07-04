"""
config_manager.py
------------------
Handles multi-client configuration. Each client's setup (Sheet ID, folder,
Canva creds, Gupshup account, etc.) is stored as a JSON file inside /clients.

Run this directly to create or edit a client:
    python config_manager.py

Both stage1_build.py and stage2_send.py import load_client() from here.
"""

import os
import json

CLIENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clients")
os.makedirs(CLIENTS_DIR, exist_ok=True)


# ---- the fields every client config holds ----
FIELDS = [
    ("client_name",        "Client name (used as folder/label, e.g. euro_school)", True),
    ("sheet_id",           "Google Sheet ID (the long string in the sheet URL)", True),
    ("sheet_tab",          "Sheet tab/worksheet name (e.g. Sheet1)", True),
    ("image_col",          "Column header holding the image (local filename OR http link)", True),
    ("number_col",         "Column header holding the WhatsApp number", True),
    ("local_images_dir",   "Full path to the LOCAL images folder", True),
    ("service_account",    "Full path to Google service-account .json", True),
    ("canva_template_url", "Canva template URL (reference only - you open it manually)", False),
    ("gupshup_api_key",    "Gupshup API key", True),
    ("gupshup_source",     "Gupshup source number (your registered WhatsApp sender, e.g. 917xxxxxxxxx)", True),
    ("gupshup_app_name",   "Gupshup app name", True),
    ("gupshup_template_id","Gupshup approved TEMPLATE ID (image-header template)", True),
    ("host_bucket_url",    "Public host base URL for images (Supabase/Drive folder public URL)", True),
]


def _prompt(label, required):
    while True:
        val = input(f"  {label}:\n    > ").strip()
        if val or not required:
            return val
        print("    ! required, please enter a value.")


def create_or_edit_client():
    print("\n=== Client Setup ===")
    existing = list_clients()
    if existing:
        print(f"Existing clients: {', '.join(existing)}")
    name = input("Client name to create/edit (blank to cancel): ").strip()
    if not name:
        return None

    path = _client_path(name)
    prefill = {}
    if os.path.exists(path):
        with open(path) as f:
            prefill = json.load(f)
        print(f"Editing existing client '{name}'. Press Enter to keep current value.\n")

    cfg = {}
    for key, label, required in FIELDS:
        current = prefill.get(key, "")
        if key == "client_name":
            cfg[key] = name
            continue
        shown = f"{label}" + (f"  [current: {current}]" if current else "")
        val = input(f"  {shown}:\n    > ").strip()
        if not val and current:
            cfg[key] = current
        elif not val and required:
            while not val:
                val = input("    ! required > ").strip()
            cfg[key] = val
        else:
            cfg[key] = val

    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"\nSaved: {path}\n")
    return name


def _client_path(name):
    safe = name.strip().lower().replace(" ", "_")
    return os.path.join(CLIENTS_DIR, f"{safe}.json")


def list_clients():
    return [f[:-5] for f in os.listdir(CLIENTS_DIR) if f.endswith(".json")]


def load_client(name=None):
    """Load a client config. If name is None, prompt to pick one."""
    clients = list_clients()
    if not clients:
        raise SystemExit("No clients configured. Run: python config_manager.py")

    if name is None:
        print("\nAvailable clients:")
        for i, c in enumerate(clients, 1):
            print(f"  {i}. {c}")
        choice = input("Pick client (number or name): ").strip()
        if choice.isdigit():
            name = clients[int(choice) - 1]
        else:
            name = choice

    path = _client_path(name)
    if not os.path.exists(path):
        raise SystemExit(f"Client '{name}' not found.")
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    while True:
        create_or_edit_client()
        if input("\nAdd/edit another client? (y/N): ").strip().lower() != "y":
            break
    print("Done.")
