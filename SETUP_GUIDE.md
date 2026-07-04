# Setup Guide — Canva → WhatsApp Sender

This tool takes images (from a folder or from links in your Google Sheet),
puts them into your Canva template, and sends the finished designs to the
WhatsApp numbers in your sheet.

You only ever run **one thing**. No coding.

---

## What you need before starting

Gather these — ask your provider if you don't have any of them:

1. **A Google Sheet** with two columns: one for the image, one for the WhatsApp number.
2. **Your images** — either as files in a folder on this PC, or as links in the sheet.
3. **A Google service-account file** (a `.json` file you were given).
4. **Your Canva template link.**
5. **Your Gupshup details:** API key, sender number, app name, and approved template ID.
6. **An image host link** (Supabase or a public folder URL — your provider sets this up).

---

## First-time install (once)

1. Install **Python 3.10+** from python.org — during install, tick
   **"Add Python to PATH"**.
2. Open the tool folder. In the address bar type `cmd` and press Enter.
3. Run these two lines (copy-paste, press Enter after each):
   ```
   pip install -r requirements.txt
   python -m playwright install chromium
   ```
That's the install done.

---

## How to use it

**Windows:** double-click **`START.bat`**
**Or from CMD:** `python run.py`

You'll see a menu:

```
  1. Set up / edit my account details
  2. Test my connections
  3. Run a batch
  4. Exit
```

### Step 1 — Set up (do this once)
Choose **1**. It asks for your details one at a time. Paste each, press Enter.

### Step 2 — Test (do this after setup)
Choose **2**. It checks your Google Sheet and Gupshup actually work and tells
you in plain English if something's wrong (e.g. "sheet isn't shared").

### Step 3 — Run a batch (every time you want to send)
Choose **3**. It will:
1. Read your sheet and prepare the images.
2. Open Canva and fill your template automatically.
   - If Canva's layout changed and it can't click something, it **pauses and
     tells you the few clicks to do by hand**, then you press Enter to continue.
     You will never get stuck.
3. Ask you to confirm, then send everything on WhatsApp.

---

## Your sheet format

| image | number |
|-------|--------|
| photo1.png | 9198xxxxxxx |
| https://drive.google.com/file/d/XXXX/view | 9198xxxxxxx |

- If the cell starts with `http` it's treated as a **link** (downloaded automatically).
- Otherwise it's treated as a **filename** in your images folder.
- Numbers with country code, no `+` (e.g. `9198…`).

---

## If something goes wrong

- **"Sheet isn't shared"** → open your Google Sheet → Share → add the
  service-account email (it ends in `...iam.gserviceaccount.com`) as Viewer.
- **"File not found"** → check your images folder path in setup (option 1).
- **Canva step won't click** → choose manual mode when asked; the tool lists
  the exact clicks.
- **WhatsApp not sending** → run "Test my connections" (option 2) to check your
  Gupshup key, and confirm your Gupshup template is approved.

Everything the tool produces (data file, exported PDF, send log) is saved in the
`work` folder inside the tool, organised by your account name.
