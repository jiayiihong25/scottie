"""Google Drive client authenticated as a service account."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .sync import DriveItem

_SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveClient:
    def __init__(self, service_account_info: dict) -> None:
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=_SCOPES
        )
        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    @classmethod
    def from_env(cls) -> GoogleDriveClient:
        load_dotenv()
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not raw:
            raise RuntimeError(
                "GOOGLE_SERVICE_ACCOUNT_JSON must be set (env var or .env) — "
                "the service account key's JSON contents"
            )
        return cls(json.loads(raw))

    def list_children(self, folder_id: str) -> list[DriveItem]:
        items: list[DriveItem] = []
        token = None
        while True:
            resp = (
                self._svc.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageSize=1000,
                    pageToken=token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items += [DriveItem(f["id"], f["name"], f["mimeType"]) for f in resp["files"]]
            token = resp.get("nextPageToken")
            if not token:
                return items

    def download(self, file_id: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = self._svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        with open(dest, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

    def update_content(self, file_id: str, src: Path) -> None:
        media = MediaFileUpload(str(src), resumable=False)
        self._svc.files().update(
            fileId=file_id, media_body=media, supportsAllDrives=True
        ).execute()
