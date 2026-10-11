# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Outlook .msg is an OLE2 compound file, not a stream format — extract-msg
# (built on olefile) needs a real file path, so the uploaded bytes are
# written to a temp file for the duration of the parse. No writer library
# exists for .msg (it's Outlook's native binary format), so unlike every
# other parser here this one isn't exercised by a real-file round-trip unit
# test — only against extract-msg's documented attribute surface.

import tempfile
from pathlib import Path
from typing import BinaryIO

import extract_msg

from app.ingestion.parsers.base import ParsedElement, Parser


class MsgParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "message.msg"
            tmp_path.write_bytes(file.read())

            message = extract_msg.openMsg(str(tmp_path))
            try:
                elements: list[ParsedElement] = []

                header_lines = [
                    f"{label}: {value}"
                    for label, value in (
                        ("Subject", message.subject),
                        ("From", message.sender),
                        ("To", message.to),
                        ("Date", message.date),
                    )
                    if value
                ]
                if header_lines:
                    elements.append(
                        ParsedElement(content="\n".join(header_lines), metadata={"kind": "header"})
                    )

                body = (message.body or "").strip()
                if body:
                    attachment_names = [
                        attachment.longFilename or attachment.shortFilename
                        for attachment in message.attachments
                        if attachment.longFilename or attachment.shortFilename
                    ]
                    metadata = {"kind": "body"}
                    if attachment_names:
                        metadata["attachments"] = attachment_names
                    elements.append(ParsedElement(content=body, metadata=metadata))

                return elements
            finally:
                message.close()
