"""
stage2_send.py
--------------
STAGE 2 of the pipeline (fully automatic).

  1. Finds the exported PDF in the client's /export folder
  2. Splits it page-by-page -> PNGs  (page order == manifest order == row order)
  3. For each page:
        - uploads the PNG so Gupshup can fetch a public URL
        - sends the Gupshup approved image-header TEMPLATE to that row's number
  4. Writes send_log.json with per-number success/failure

Ordering is guaranteed: PDF page N  ->  manifest.rows[N]  ->  that row's number.
Because of that, DO NOT reorder pages during Canva export.

Run:
    python stage2_send.py
"""

import os
import io
import json
import glob
import time
import requests
from datetime import datetime

import fitz  # PyMuPDF
from config_manager import load_client


# ---------- image hosting ----------
# Gupshup needs a PUBLIC URL for the image. Two host modes are supported:
#   host_bucket_url starting with "supabase:"  -> Supabase Storage upload
#   otherwise treated as a plain base URL you serve the /pages folder from
#
# Simplest robust option: Supabase. Format the host_bucket_url as:
#   supabase:https://<proj>.supabase.co|<bucket>|<service_role_key>
def upload_image(cfg, local_png, filename):
    host = cfg["host_bucket_url"]

    if host.startswith("supabase:"):
        _, rest = host.split("supabase:", 1)
        proj_url, bucket, key = rest.split("|")
        up_url = f"{proj_url}/storage/v1/object/{bucket}/{filename}"
        with open(local_png, "rb") as f:
            data = f.read()
        r = requests.post(
            up_url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "image/png",
                "x-upsert": "true",
            },
            data=data,
            timeout=60,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Supabase upload failed {r.status_code}: {r.text}")
        return f"{proj_url}/storage/v1/object/public/{bucket}/{filename}"

    # plain base URL mode: assumes you separately serve the pages folder publicly
    base = host.rstrip("/")
    return f"{base}/{filename}"


# ---------- Gupshup send ----------
def send_gupshup(cfg, to_number, image_url, page_no):
    """
    Sends an approved image-header template message via Gupshup.
    Template messages are required for business-initiated (broadcast) sends.
    """
    url = "https://api.gupshup.io/wa/api/v1/template/msg"
    payload = {
        "channel": "whatsapp",
        "source": cfg["gupshup_source"],
        "destination": to_number,
        "src.name": cfg["gupshup_app_name"],
        "template": json.dumps({
            "id": cfg["gupshup_template_id"],
            "params": [],  # add text params here if your template has body variables
        }),
        "message": json.dumps({
            "type": "image",
            "image": {"link": image_url},
        }),
    }
    headers = {
        "apikey": cfg["gupshup_api_key"],
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r = requests.post(url, data=payload, headers=headers, timeout=60)
    ok = r.status_code == 202 or r.status_code == 200
    return ok, r.status_code, r.text


def find_pdf(export_dir):
    pdfs = glob.glob(os.path.join(export_dir, "*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF found in {export_dir}. Export the Canva batch there first.")
    if len(pdfs) > 1:
        pdfs.sort(key=os.path.getmtime, reverse=True)
        print(f"  ! multiple PDFs found, using newest: {os.path.basename(pdfs[0])}")
    return pdfs[0]


def split_pdf(pdf_path, pages_dir, dpi=200):
    os.makedirs(pages_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        out = os.path.join(pages_dir, f"page_{i:04d}.png")
        pix.save(out)
        paths.append(out)
    doc.close()
    return paths


def run(cfg):
    client = cfg["client_name"]
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", client)
    export_dir = os.path.join(base, "export")
    pages_dir = os.path.join(base, "pages")
    manifest_path = os.path.join(base, "manifest.json")

    if not os.path.exists(manifest_path):
        raise SystemExit("manifest.json missing. Run stage1_build.py first.")
    with open(manifest_path) as f:
        manifest = json.load(f)
    rows = manifest["rows"]

    print(f"\n[Stage 2] Client: {client}")
    pdf_path = find_pdf(export_dir)
    print(f"  PDF: {os.path.basename(pdf_path)}")
    print("  Splitting pages...")
    pages = split_pdf(pdf_path, pages_dir)
    print(f"  {len(pages)} pages.")

    if len(pages) != len(rows):
        print(f"\n  !! WARNING: {len(pages)} pages but manifest has {len(rows)} rows.")
        print("     Order matching may be off. Check the Canva export before sending.")
        if input("     Continue anyway? (y/N): ").strip().lower() != "y":
            raise SystemExit("Aborted.")

    log = []
    for i, page_png in enumerate(pages):
        if i >= len(rows):
            break
        number = rows[i]["number"]
        fname = f"{client}_{i:04d}_{int(time.time())}.png"
        try:
            public_url = upload_image(cfg, page_png, fname)
        except Exception as e:
            print(f"  page {i} -> {number}: UPLOAD FAILED ({e})")
            log.append({"order": i, "number": number, "status": "upload_failed", "error": str(e)})
            continue

        ok, code, resp = send_gupshup(cfg, number, public_url, i)
        status = "sent" if ok else "send_failed"
        print(f"  page {i} -> {number}: {status} ({code})")
        log.append({
            "order": i, "number": number, "status": status,
            "http": code, "image_url": public_url,
            "response": resp[:300],
        })
        time.sleep(1.2)  # gentle pacing

    log_path = os.path.join(base, f"send_log_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2)

    sent = sum(1 for x in log if x["status"] == "sent")
    print(f"\n[Stage 2 done] {sent}/{len(log)} sent.")
    print(f"  log: {log_path}")


if __name__ == "__main__":
    cfg = load_client()
    run(cfg)
