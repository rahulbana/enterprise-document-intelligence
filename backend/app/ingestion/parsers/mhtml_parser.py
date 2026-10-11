# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# MHTML is a MIME envelope (same format email uses) wrapping an HTML part
# plus its inline resources — stdlib `email` unwraps the MIME structure to
# find the text/html part, then it's the same heading-sectioning logic as
# HtmlParser.

from email import message_from_bytes
from email.message import Message
from typing import BinaryIO

from app.ingestion.parsers._html_common import elements_from_html
from app.ingestion.parsers.base import ParsedElement, Parser


class MhtmlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        message = message_from_bytes(file.read())
        html_part = self._find_html_part(message)
        if html_part is None:
            return []

        payload = html_part.get_payload(decode=True)
        charset = html_part.get_content_charset() or "utf-8"
        html = payload.decode(charset, errors="replace") if payload else ""
        return elements_from_html(html)

    @staticmethod
    def _find_html_part(message: Message) -> Message | None:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/html":
                    return part
            return None
        if message.get_content_type() == "text/html":
            return message
        return None
