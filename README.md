# Canva → WhatsApp Bulk Tool (multi-client)

Sends images (from a local folder **or** sheet links) into a fixed Canva
template, then delivers each finished card to a WhatsApp number via Gupshup.

**One codebase, many clients.** Each client is a saved config. You set a
client up once, then reuse it every run.

---

## The flow (3 parts)

```
STAGE 1  (auto)              YOU  (manual, in Canva)          STAGE 2  (auto)
---------------              -----------------------          ---------------
read sheet                   open template                    find exported PDF
resolve images               Bulk Create -> upload xlsx        split pages (in order)
build bulk.xlsx      ---->    bind Image field       ---->     upload each page
write manifest.json          export batch as ONE PDF           Gupshup send -> number
```

The Canva middle step is manual because Canva's automatic autofill API
requires the Enterprise plan. Everything before and after it is automatic.

---

## Install (one time)

```
pip install -r requirements.txt
```

## Step 1 — set up a client (one time per client)

```
python config_manager.py
```

It asks for:
- Google Sheet ID + tab name
- the image column header + number column header
- local images folder path
- Google service-account .json path (must be shared on the sheet)
- Canva template URL (reference only)
- Gupshup: API key, source number, app name, approved template ID
- image host base URL (see "Hosting" below)

Saved to `clients/<name>.json`. Re-run anytime to edit.

### Sheet format
Two columns matter (any headers, you name them in config):
| image | number |
|-------|--------|
| aarav.png | 9198xxxxxxx |
| https://drive.google.com/file/d/XXXX/view | 9198xxxxxxx |

Rule: value starts with `http` → treated as a link (downloaded).
Otherwise → treated as a filename inside your local images folder.

### Hosting (for Gupshup)
Gupshup needs a public image URL. Easiest = Supabase. Set the host field to:
```
supabase:https://<proj>.supabase.co|<bucket-name>|<service-role-key>
```
Or, if you serve the pages folder publicly yourself, just put the base URL.

### Gupshup template
Business-initiated WhatsApp sends require an **approved template**. Create an
**image-header template** in Gupshup and put its template ID in config. The
code sends the split page as the image header of that template.

## Step 2 — build the batch

```
python stage1_build.py
```
Pick the client. It produces `work/<client>/<client>_bulk.xlsx` and a manifest.

## Step 3 — Canva (now automated via browser)

**Playwright must be installed once:**
```
pip install playwright
python -m playwright install chromium
```

**One-time login per client** (opens a visible browser, you log into that
client's Canva, session is saved):
```
python stage1_5_canva.py --login
```

**Then run the automation:**
```
python stage1_5_canva.py
```
It opens the template, runs Bulk Create with the xlsx, binds the image field,
generates pages, and exports the PDF into `work/<client>/export/`.

⚠️ **This step is fragile by nature.** It drives Canva's real UI, so when Canva
changes a button the script pauses and drops a screenshot in
`work/<client>/debug/`. Update the matching selector in `stage1_5_canva.py`.
The image-binding step may need one manual click the first time — the script
will pause and tell you when.

If you'd rather do it by hand: open the template → Bulk Create → upload the
xlsx → connect the Image field → export as ONE PDF into
`work/<client>/export/`. Do not reorder pages (page order = row order = number).

## Step 4 — send

```
python stage2_send.py
```
Splits the PDF, uploads each page, sends via Gupshup, writes `send_log_*.json`.

---

## Notes
- 100 sends is fine on Gupshup (official API, no ban risk).
- Rows with no number, or with a missing/broken image, are skipped and logged.
- Page count mismatch vs manifest triggers a warning before sending.
