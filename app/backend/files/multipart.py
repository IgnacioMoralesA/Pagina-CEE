from __future__ import annotations

from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default

from fastapi import Request

from app.backend.core.errors import AppError
from app.backend.files.storage import UploadedFilePayload


MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024


@dataclass(frozen=True)
class ParsedMultipart:
    fields: dict[str, str]
    file: UploadedFilePayload


async def parse_multipart_upload(
    request: Request,
    *,
    max_file_size_bytes: int,
) -> ParsedMultipart:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type.lower():
        raise AppError(status_code=415, message="Contenido multipart requerido")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_file_size_bytes + MAX_MULTIPART_OVERHEAD_BYTES:
                raise AppError(status_code=413, message="Archivo demasiado grande")
        except ValueError:
            raise AppError(status_code=400, message="Cabecera Content-Length invalida")

    body = await _read_limited_body(
        request,
        max_bytes=max_file_size_bytes + MAX_MULTIPART_OVERHEAD_BYTES,
    )

    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: "
        + content_type.encode("utf-8")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body
    )
    if not message.is_multipart():
        raise AppError(status_code=400, message="Multipart invalido")

    fields: dict[str, str] = {}
    uploaded_file: UploadedFilePayload | None = None
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is None:
            if name:
                charset = part.get_content_charset() or "utf-8"
                fields[str(name)] = payload.decode(charset, errors="replace")
            continue
        if uploaded_file is not None:
            raise AppError(status_code=422, message="Solo se permite un archivo")
        uploaded_file = UploadedFilePayload(
            filename=filename,
            content_type=part.get_content_type(),
            content=payload,
        )

    if uploaded_file is None:
        raise AppError(status_code=422, message="Archivo obligatorio")

    return ParsedMultipart(fields=fields, file=uploaded_file)


async def _read_limited_body(request: Request, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise AppError(status_code=413, message="Archivo demasiado grande")
        chunks.append(chunk)
    return b"".join(chunks)
