"""
בלוק 1 — הורדה מדרייב
קלט: DRIVE_FOLDER_ID (מה-.env)
פלט: קובץ אודיו/וידאו מקומי בתיקיית data/
"""
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH"),
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds)


def find_latest_recording(service, name_contains="טירונות סוכנים"):
    """
    מוצא את קובץ האודיו/וידאו האחרון ששותף עם ה-Service Account,
    ששמו מכיל את name_contains (במקום להסתמך על תיקייה — שלהבת
    משתפת את הקבצים עצמם, לא תיקייה).
    """
    results = (
        service.files()
        .list(
            q=(
                "sharedWithMe = true and "
                f"name contains '{name_contains}' and "
                "(mimeType contains 'audio/' or mimeType contains 'video/') and "
                "trashed = false"
            ),
            fields="files(id, name, mimeType, createdTime)",
            orderBy="createdTime desc",
            pageSize=1,
        )
        .execute()
    )
    files = results.get("files", [])
    if not files:
        raise FileNotFoundError(
            "לא נמצא קובץ אודיו/וידאו משותף עם ה-Service Account. "
            "ודא ששלהבת שיתפה את הקובץ ישירות עם "
            "drive-reader@aimprove-pipeline-503321.iam.gserviceaccount.com "
            "(Viewer)."
        )
    return files[0]


def download_file(service, file_id, file_name, dest_dir="data"):
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file_name)
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def download_latest_lesson(dest_dir="data"):
    """נקודת הכניסה של הבלוק — מוצא ומוריד את השיעור האחרון."""
    service = get_drive_service()
    file_meta = find_latest_recording(service)
    print(f"נמצא קובץ: {file_meta['name']} — מוריד...")
    path = download_file(service, file_meta["id"], file_meta["name"], dest_dir)
    print(f"הורד ל: {path}")
    return path


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    download_latest_lesson()
