# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# One header + one body element per message, same shape as EmlParser (an
# mbox is just a sequence of RFC 822 messages). stdlib mailbox.mbox wants a
# real file path, so the uploaded bytes are written to a temp file for the
# duration of the parse.

import mailbox
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.ingestion.parsers._email_common import elements_from_email_message
from app.ingestion.parsers.base import ParsedElement, Parser


class MboxParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "messages.mbox"
            tmp_path.write_bytes(file.read())

            elements: list[ParsedElement] = []
            box = mailbox.mbox(str(tmp_path))
            try:
                for index, message in enumerate(box):
                    elements.extend(
                        elements_from_email_message(
                            message, extra_metadata={"message_index": index}
                        )
                    )
            finally:
                box.close()
            return elements
