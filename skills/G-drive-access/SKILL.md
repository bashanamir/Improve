---
name: gdrive-access
description: Access Google Drive programmatically via a Service Account — list, search, and download files or entire folders. Use whenever the user wants a script/pipeline/agent to read from their Google Drive automatically (not through the claude.ai/Cowork Drive connector, but as standalone Python code they run themselves, e.g. in a local pipeline or scheduled job). Works with any folder or file, not tied to a specific one. Trigger on phrases like "pull files from Drive", "download my Drive folder", "watch this Drive folder for new files", "גישה לדרייב", "תוריד מהתיקייה בדרייב".
---

# Google Drive Access (Service Account)

A generic Google Drive access layer for standalone scripts/pipelines/agents
— extracted from a lesson-recording downloader, generalized to work with
any file or folder the service account has been granted access to.

## When to use this vs. the built-in Drive connector

- **This skill**: for code the user runs themselves outside claude.ai —
  a local pipeline, a scheduled job, an agent running unattended on their
  machine. Needs its own service account credentials.
- **The built-in Google Drive connector** (if available in the current
  session's tools): for browsing/reading the user's Drive *within this
  conversation*, right now. Don't reach for this skill for that — use the
  connector tool directly, it's simpler and needs no setup.

## How Drive access actually works with a Service Account

This is the part people get stuck on, so front-load it: **a service
account does not automatically see anything in a user's personal Drive.**
Access only exists for files/folders explicitly shared with the service
account's own email address (looks like
`something@project-id.iam.gserviceaccount.com`), the same way you'd share
a file with any other person.

So the setup, once, is:
1. Create a service account in Google Cloud Console, enable the Drive API,
   download its JSON key.
2. In Google Drive, share the specific file or folder with the service
   account's email (Viewer is enough for read-only use).
3. Point `GOOGLE_SERVICE_ACCOUNT_PATH` at the downloaded JSON key (env var
   or `.env` file).

After that, this skill can see anything shared that way — any folder, any
number of folders, not just one hardcoded target.

## Prerequisites

```bash
pip install -r scripts/requirements.txt --break-system-packages
```

`.env` (or environment variables):
```
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json
```

## How to use it

Everything goes through `scripts/drive_access.py`. Don't reimplement the
Drive API calls inline — call this script, or import its functions
(`get_drive_service`, `list_files`, `find_file`, `download_file`,
`download_folder`) directly in Python if building something more custom.

### List files
```bash
# Everything shared directly with the service account
python scripts/drive_access.py list --shared-with-me

# Contents of a specific folder (by folder ID, from the Drive URL)
python scripts/drive_access.py list --folder-id 1AbC...xyz

# Filter by name and/or type, combinable with any of the above
python scripts/drive_access.py list --folder-id 1AbC...xyz --name-contains "invoice" --mime-contains "application/pdf"
```

### Find a single file
```bash
python scripts/drive_access.py find "quarterly report" --folder-id 1AbC...xyz
```
Returns the most recently created match. Useful for "get me the latest X"
type lookups.

### Download one file
```bash
python scripts/drive_access.py download 1AbC...xyz --dest ./downloads
```

### Download a whole folder (recurses into subfolders by default)
```bash
python scripts/drive_access.py download-folder 1AbC...xyz --dest ./downloads
python scripts/drive_access.py download-folder 1AbC...xyz --dest ./downloads --no-recursive
```

## Using it as a library instead of a CLI

For pipelines that need to branch on results (e.g. "if a new file showed
up since last run, download and process it"), import the functions
directly instead of shelling out:

```python
from drive_access import get_drive_service, find_file, download_file

service = get_drive_service()
match = find_file(service, name_contains="Weekly Report", folder_id=FOLDER_ID)
if match:
    path = download_file(service, match["id"], match["name"], dest_dir="data")
```

## Read-only by default

The script requests `drive.readonly` scope only — it cannot upload, edit,
or delete anything. If a use case genuinely needs write access (e.g.
uploading a processed result back to Drive), that requires widening the
`SCOPES` list in `drive_access.py` to `https://www.googleapis.com/auth/drive`
and adding upload logic — treat that as a deliberate, separate extension,
not something to do by default.

## Common gotcha

If `list`/`find`/`download` comes back empty for something you know
exists: the file almost certainly hasn't been shared with the service
account's email yet. That's the #1 cause of "it can't find anything" —
not a code bug.
