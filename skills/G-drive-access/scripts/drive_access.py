#!/usr/bin/env python3
"""
Generic Google Drive access via a Service Account.

Lists, finds, and downloads files from ANY Drive folder the service
account has been given access to — not tied to any specific folder,
file name pattern, or file type. Read-only by default.

Usage examples:
    # List everything shared directly with the service account
    python drive_access.py list --shared-with-me

    # List the contents of a specific folder (by folder ID)
    python drive_access.py list --folder-id 1AbC...xyz

    # Find files by name (substring match), optionally scoped to a folder
    python drive_access.py find "quarterly report" --folder-id 1AbC...xyz

    # Download a single file by its ID
    python drive_access.py download 1AbC...xyz --dest ./downloads

    # Download every file in a folder (recurses into subfolders)
    python drive_access.py download-folder 1AbC...xyz --dest ./downloads

Requires:
    pip install google-api-python-client google-auth python-dotenv

Environment:
    GOOGLE_SERVICE_ACCOUNT_PATH — path to the service account JSON key
    (set in the environment or a .env file in the current directory)
"""
import argparse
import io
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

FOLDER_MIME = "application/vnd.google-apps.folder"


def get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
    if not key_path or not os.path.exists(key_path):
        sys.exit(
            "GOOGLE_SERVICE_ACCOUNT_PATH is not set or the file doesn't exist. "
            "Set it as an environment variable or in a .env file, pointing "
            "at the service account JSON key downloaded from Google Cloud Console."
        )
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _build_query(folder_id=None, name_contains=None, mime_contains=None,
                  shared_with_me=False, include_trashed=False):
    """Builds a Drive API v3 query string from the given, all-optional filters."""
    clauses = []
    if folder_id:
        clauses.append(f"'{folder_id}' in parents")
    if name_contains:
        escaped = name_contains.replace("'", "\\'")
        clauses.append(f"name contains '{escaped}'")
    if mime_contains:
        clauses.append(f"mimeType contains '{mime_contains}'")
    if shared_with_me:
        clauses.append("sharedWithMe = true")
    if not include_trashed:
        clauses.append("trashed = false")
    return " and ".join(clauses) if clauses else "trashed = false"


def list_files(service, folder_id=None, name_contains=None, mime_contains=None,
               shared_with_me=False, order_by="createdTime desc", page_size=50):
    """
    Generic listing — every argument is optional so this works for any
    combination: a specific folder, a name/type filter, everything shared
    with the service account, or all of the above together.
    """
    query = _build_query(folder_id, name_contains, mime_contains, shared_with_me)
    all_files = []
    page_token = None
    while True:
        results = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents)",
                orderBy=order_by,
                pageSize=min(page_size, 1000),
                pageToken=page_token,
            )
            .execute()
        )
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token or len(all_files) >= page_size:
            break
    return all_files[:page_size]


def find_file(service, name_contains, folder_id=None, mime_contains=None, shared_with_me=False):
    """Returns the single most-recently-created match, or None."""
    matches = list_files(
        service, folder_id=folder_id, name_contains=name_contains,
        mime_contains=mime_contains, shared_with_me=shared_with_me, page_size=1,
    )
    return matches[0] if matches else None


def download_file(service, file_id, file_name=None, dest_dir="."):
    """Downloads a single file by ID. Fetches the name automatically if not given."""
    if file_name is None:
        meta = service.files().get(fileId=file_id, fields="name").execute()
        file_name = meta["name"]

    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file_name)

    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def download_folder(service, folder_id, dest_dir=".", recursive=True, _depth=0):
    """
    Downloads every file in a folder, preserving subfolder structure if
    recursive=True (the default). Returns a list of local paths written.
    """
    downloaded = []
    entries = list_files(service, folder_id=folder_id, page_size=1000)

    for entry in entries:
        if entry["mimeType"] == FOLDER_MIME:
            if recursive:
                sub_dest = os.path.join(dest_dir, entry["name"])
                downloaded.extend(
                    download_folder(service, entry["id"], sub_dest, recursive=True, _depth=_depth + 1)
                )
            continue

        indent = "  " * _depth
        print(f"{indent}downloading: {entry['name']}")
        path = download_file(service, entry["id"], entry["name"], dest_dir)
        downloaded.append(path)

    return downloaded


def _print_files(files):
    if not files:
        print("(no files matched)")
        return
    for f in files:
        size = f.get("size")
        size_str = f"{int(size)/1_000_000:.1f}MB" if size else "-"
        kind = "folder" if f["mimeType"] == FOLDER_MIME else f["mimeType"]
        print(f"{f['id']}  {f['name']}  [{kind}]  {size_str}  created {f.get('createdTime', '-')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List files matching optional filters")
    p_list.add_argument("--folder-id", help="Only list contents of this folder")
    p_list.add_argument("--name-contains", help="Substring filter on file name")
    p_list.add_argument("--mime-contains", help="Substring filter on MIME type, e.g. 'audio/', 'image/'")
    p_list.add_argument("--shared-with-me", action="store_true", help="Only files shared directly with the service account")
    p_list.add_argument("--page-size", type=int, default=50)

    p_find = sub.add_parser("find", help="Find the most recent single file matching a name substring")
    p_find.add_argument("name_contains")
    p_find.add_argument("--folder-id")
    p_find.add_argument("--mime-contains")
    p_find.add_argument("--shared-with-me", action="store_true")

    p_dl = sub.add_parser("download", help="Download a single file by ID")
    p_dl.add_argument("file_id")
    p_dl.add_argument("--dest", default=".", help="Destination directory")

    p_dlf = sub.add_parser("download-folder", help="Download every file in a folder")
    p_dlf.add_argument("folder_id")
    p_dlf.add_argument("--dest", default=".", help="Destination directory")
    p_dlf.add_argument("--no-recursive", action="store_true", help="Don't descend into subfolders")

    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    service = get_drive_service()

    if args.command == "list":
        files = list_files(
            service, folder_id=args.folder_id, name_contains=args.name_contains,
            mime_contains=args.mime_contains, shared_with_me=args.shared_with_me,
            page_size=args.page_size,
        )
        _print_files(files)

    elif args.command == "find":
        match = find_file(
            service, args.name_contains, folder_id=args.folder_id,
            mime_contains=args.mime_contains, shared_with_me=args.shared_with_me,
        )
        _print_files([match] if match else [])

    elif args.command == "download":
        path = download_file(service, args.file_id, dest_dir=args.dest)
        print(f"Downloaded to: {path}")

    elif args.command == "download-folder":
        paths = download_folder(service, args.folder_id, dest_dir=args.dest, recursive=not args.no_recursive)
        print(f"\nDownloaded {len(paths)} file(s) to: {args.dest}")


if __name__ == "__main__":
    main()
