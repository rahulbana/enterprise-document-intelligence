# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Shared "stdlib email.message.Message -> elements" logic for EmlParser and
# MboxParser (each message in an mbox is the same Message type EML uses).
# Two elements per message: headers (subject/from/to/date) and body (prefers
# text/plain, falls back to text/html stripped of tags). Attachments are
# named in metadata but their content isn't extracted — same scope boundary
# as PptxParser's images (presence/location retrievable, not OCR'd).

from email.message import Message
from typing import Any

from bs4 import BeautifulSoup

from app.ingestion.parsers.base import ParsedElement


def elements_from_email_message(
    message: Message, *, extra_metadata: dict[str, Any] | None = None
) -> list[ParsedElement]:
    base_metadata = dict(extra_metadata or {})

    header_lines = [
        f"{field}: {message.get(field, '')}"
        for field in ("Subject", "From", "To", "Date")
        if message.get(field)
    ]
    elements: list[ParsedElement] = []
    if header_lines:
        elements.append(
            ParsedElement(
                content="\n".join(header_lines), metadata={**base_metadata, "kind": "header"}
            )
        )

    body_text = _body_text(message)
    attachments = _attachment_names(message)
    if body_text:
        metadata = {**base_metadata, "kind": "body"}
        if attachments:
            metadata["attachments"] = attachments
        elements.append(ParsedElement(content=body_text, metadata=metadata))

    return elements


def _body_text(message: Message) -> str:
    plain, html = None, None
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain" and plain is None:
                plain = _decode(part)
            elif part.get_content_type() == "text/html" and html is None:
                html = _decode(part)
    elif message.get_content_type() == "text/plain":
        plain = _decode(message)
    elif message.get_content_type() == "text/html":
        html = _decode(message)

    if plain:
        return plain.strip()
    if html:
        return BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
    return ""


def _decode(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _attachment_names(message: Message) -> list[str]:
    if not message.is_multipart():
        return []
    return [
        part.get_filename()
        for part in message.walk()
        if part.get_content_disposition() == "attachment" and part.get_filename()
    ]
