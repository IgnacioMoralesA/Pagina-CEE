from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from app.backend.core.config import Settings
from app.backend.core.errors import AppError
from app.backend.core.responses import ErrorDetail


ALLOWED_MIME_TYPES_BY_EXTENSION: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    ".csv": {"text/csv"},
}


@dataclass(frozen=True)
class UploadedFilePayload:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class StoredFileMetadata:
    storage_key: str
    file_name: str
    mime_type: str
    file_size_bytes: int
    sha256: str


class LocalFileStorage:
    def __init__(self, settings: Settings) -> None:
        self.max_upload_size_bytes = settings.max_upload_size_bytes
        self.base_path = Path(settings.file_storage_path).resolve()

    def store(
        self,
        upload: UploadedFilePayload,
        *,
        bucket: str,
    ) -> StoredFileMetadata:
        file_name, extension = _safe_public_file_name(upload.filename)
        mime_type = _normalized_mime_type(upload.content_type)
        _ensure_mime_matches_extension(extension, mime_type)
        file_size = len(upload.content)
        if file_size == 0:
            raise AppError(status_code=422, message="Archivo vacio")
        if file_size > self.max_upload_size_bytes:
            raise AppError(status_code=413, message="Archivo demasiado grande")
        _ensure_content_matches_extension(extension, upload.content)

        storage_key = f"{_safe_bucket(bucket)}/{uuid4().hex}{extension}"
        target_path = self.resolve_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(upload.content)

        sha256 = hashlib.sha256(upload.content).hexdigest()
        metadata = StoredFileMetadata(
            storage_key=storage_key,
            file_name=file_name,
            mime_type=mime_type,
            file_size_bytes=file_size,
            sha256=sha256,
        )
        self._metadata_path(target_path).write_text(
            json.dumps(
                {
                    "storage_key": metadata.storage_key,
                    "file_name": metadata.file_name,
                    "mime_type": metadata.mime_type,
                    "file_size_bytes": metadata.file_size_bytes,
                    "sha256": metadata.sha256,
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        return metadata

    def resolve_path(self, storage_key: str) -> Path:
        relative = PurePosixPath(storage_key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise AppError(status_code=404, message="Archivo no encontrado")
        path = (self.base_path / Path(*relative.parts)).resolve()
        try:
            path.relative_to(self.base_path)
        except ValueError as exc:
            raise AppError(status_code=404, message="Archivo no encontrado") from exc
        return path

    def get_metadata(self, storage_key: str) -> StoredFileMetadata | None:
        path = self.resolve_path(storage_key)
        metadata_path = self._metadata_path(path)
        if not metadata_path.exists():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            return StoredFileMetadata(
                storage_key=str(payload["storage_key"]),
                file_name=str(payload["file_name"]),
                mime_type=str(payload["mime_type"]),
                file_size_bytes=int(payload["file_size_bytes"]),
                sha256=str(payload["sha256"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def remove_uncommitted(self, storage_key: str) -> None:
        path = self.resolve_path(storage_key)
        metadata_path = self._metadata_path(path)
        if path.exists():
            path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()

    def _metadata_path(self, path: Path) -> Path:
        return path.with_name(f"{path.name}.json")


def _safe_public_file_name(filename: str) -> tuple[str, str]:
    raw_name = PurePosixPath(filename.replace("\\", "/")).name
    normalized = unicodedata.normalize("NFKD", raw_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.replace(" ", "_")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("._-")
    if "." not in ascii_name:
        raise AppError(
            status_code=415,
            message="Tipo de archivo no permitido",
            errors=[ErrorDetail(field="file", detail="Extension no permitida")],
        )
    stem, extension = ascii_name.rsplit(".", 1)
    extension = f".{extension.lower()}"
    if extension not in ALLOWED_MIME_TYPES_BY_EXTENSION:
        raise AppError(
            status_code=415,
            message="Tipo de archivo no permitido",
            errors=[ErrorDetail(field="file", detail="Extension no permitida")],
        )
    safe_stem = (stem or "archivo")[:120]
    return f"{safe_stem}{extension}", extension


def _normalized_mime_type(mime_type: str) -> str:
    return mime_type.split(";", 1)[0].strip().lower()


def _ensure_mime_matches_extension(extension: str, mime_type: str) -> None:
    if mime_type in ALLOWED_MIME_TYPES_BY_EXTENSION[extension]:
        return
    raise AppError(
        status_code=415,
        message="Tipo de archivo no permitido",
        errors=[ErrorDetail(field="file", detail="MIME no permitido")],
    )


def _ensure_content_matches_extension(extension: str, content: bytes) -> None:
    if extension == ".pdf" and content.startswith(b"%PDF-"):
        return
    if extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    if extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff"):
        return
    if extension == ".docx" and _office_archive_contains(content, "word/"):
        return
    if extension == ".xlsx" and _office_archive_contains(content, "xl/"):
        return
    if extension == ".csv" and _looks_like_text_csv(content):
        return
    raise AppError(
        status_code=415,
        message="Contenido de archivo no coincide con tipo declarado",
        errors=[ErrorDetail(field="file", detail="Firma de archivo invalida")],
    )


def _office_archive_contains(content: bytes, required_prefix: str) -> bool:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except BadZipFile:
        return False
    return "[Content_Types].xml" in names and any(
        name.startswith(required_prefix) for name in names
    )


def _looks_like_text_csv(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    try:
        content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    return True


def _safe_bucket(bucket: str) -> str:
    cleaned_parts = []
    for part in PurePosixPath(bucket.replace("\\", "/")).parts:
        if part in {"", ".", ".."}:
            raise AppError(status_code=400, message="Ruta de almacenamiento invalida")
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", part)
        cleaned_parts.append(cleaned[:80])
    if not cleaned_parts:
        raise AppError(status_code=400, message="Ruta de almacenamiento invalida")
    return "/".join(cleaned_parts)
