"""
stage1_build.py
---------------
STAGE 1 of the pipeline (fully automatic).

  1. Reads the client's Google Sheet
  2. For each row, resolves the image:
        - starts with http  -> download the link
        - otherwise         -> look for that filename in the local images folder
  3. Builds ONE xlsx with images embedded the way Canva Bulk Create reads them
     (legacy anchored image, object_position:1)
  4. Writes manifest.json  ->  row order + whatsapp number  (Stage 2 uses this)

Run:
    python stage1_build.py

Then YOU:
    - open the Canva template
    - Bulk Create -> upload the generated xlsx -> connect the image field
    - Export the WHOLE batch as a SINGLE PDF into the client's /export folder
    - run stage2_send.py
"""

import os
import io
import json
import requests
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from PIL import Image, ImageOps
import xlsxwriter

from config_manager import load_client

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheet_rows(cfg):
    creds = Credentials.from_service_account_file(cfg["service_account"], scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(cfg["sheet_id"])
    ws = sh.worksheet(cfg["sheet_tab"])
    records = ws.get_all_records()  # list of dicts keyed by header row
    return records


def resolve_image(value, local_dir, tmp_dir, idx):
    """Return a local file path for the image, downloading if it's a link."""
    value = str(value).strip()
    if not value:
        return None

    if value.lower().startswith("http"):
        # download link -> tmp
        try:
            # handle Google Drive share links -> direct download
            if "drive.google.com" in value:
                file_id = None
                if "/d/" in value:
                    file_id = value.split("/d/")[1].split("/")[0]
                elif "id=" in value:
                    file_id = value.split("id=")[1].split("&")[0]
                if file_id:
                    value = f"https://drive.google.com/uc?export=download&id={file_id}"
            r = requests.get(value, timeout=60)
            r.raise_for_status()
            path = os.path.join(tmp_dir, f"img_{idx:04d}.jpg")
            with open(path, "wb") as f:
                f.write(r.content)
            return path
        except Exception as e:
            print(f"    ! row {idx}: failed to download link ({e})")
            return None
    else:
        # local filename
        path = os.path.join(local_dir, value)
        if os.path.exists(path):
            return path
        print(f"    ! row {idx}: local file not found -> {path}")
        return None


def normalize_image(src_path, tmp_dir, idx):
    """EXIF-rotate, convert to RGB, cap size, re-save as jpg. Returns path."""
    try:
        im = Image.open(src_path)
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        im.thumbnail((2000, 2000))
        out = os.path.join(tmp_dir, f"norm_{idx:04d}.jpg")
        im.save(out, "JPEG", quality=85)
        return out
    except Exception as e:
        print(f"    ! row {idx}: image normalize failed ({e})")
        return None


def build(cfg):
    client = cfg["client_name"]
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", client)
    tmp_dir = os.path.join(base, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(os.path.join(base, "export"), exist_ok=True)

    print(f"\n[Stage 1] Client: {client}")
    print("Reading sheet...")
    rows = get_sheet_rows(cfg)
    print(f"  {len(rows)} rows found.")

    img_col = cfg["image_col"]
    num_col = cfg["number_col"]

    xlsx_path = os.path.join(base, f"{client}_bulk.xlsx")
    wb = xlsxwriter.Workbook(xlsx_path)
    ws = wb.add_worksheet("Sheet1")
    ws.write(0, 0, "Image")  # header Canva binds the image field to

    manifest = []
    written = 0

    for i, row in enumerate(rows, start=1):
        raw_img = row.get(img_col, "")
        number = str(row.get(num_col, "")).strip()

        if not number:
            print(f"    ! row {i}: no number, skipping")
            continue

        resolved = resolve_image(raw_img, cfg["local_images_dir"], tmp_dir, i)
        if not resolved:
            continue
        norm = normalize_image(resolved, tmp_dir, i)
        if not norm:
            continue

        excel_row = written + 1  # row 0 is header
        ws.set_row(excel_row, 140)
        ws.set_column(0, 0, 26)
        # legacy anchored image = the ONLY format Canva Bulk Create reads
        ws.insert_image(excel_row, 0, norm, {
            "object_position": 1,
            "x_scale": 0.15,
            "y_scale": 0.15,
        })

        manifest.append({
            "order": written,          # 0-based page order in the exported PDF
            "number": number,
            "source": str(raw_img),
        })
        written += 1
        print(f"    row {i}: OK -> page {written}")

    wb.close()

    manifest_path = os.path.join(base, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({
            "client": client,
            "built_at": datetime.now().isoformat(),
            "count": written,
            "rows": manifest,
        }, f, indent=2)

    print(f"\n[Stage 1 done] {written} images embedded.")
    print(f"  xlsx     : {xlsx_path}")
    print(f"  manifest : {manifest_path}")
    print(f"\nNEXT (manual in Canva):")
    print(f"  1. Open your template: {cfg.get('canva_template_url','<your template>')}")
    print(f"  2. Bulk Create -> upload the xlsx above -> bind the Image field to the photo frame")
    print(f"  3. Export the WHOLE batch as ONE PDF")
    print(f"  4. Save that PDF into:  {os.path.join(base,'export')}")
    print(f"  5. Run:  python stage2_send.py")


if __name__ == "__main__":
    cfg = load_client()
    build(cfg)
