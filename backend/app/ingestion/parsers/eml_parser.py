# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from email import message_from_bytes
from typing import BinaryIO

from app.ingestion.parsers._email_common import elements_from_email_message
from app.ingestion.parsers.base import ParsedElement, Parser


class EmlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        message = message_from_bytes(file.read())
        return elements_from_email_message(message)
