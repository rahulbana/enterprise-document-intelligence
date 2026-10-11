# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# .pst is a complex mailbox container format with no usable pure-Python
# reader (pypff needs a C build that's notoriously unreliable to install).
# The only sane option: shell out to libpst's `readpst` CLI to convert the
# whole PST into one mbox file per folder, then reuse MboxParser's own
# message-walking logic on each resulting file — the same "convert with an
# external tool, then reuse an existing parser" pattern as nothing else in
# this codebase, but the only one that actually works for this format.
# Missing `readpst` (or a failed conversion) raises, same as any other
# parser error: ingestion_service catches it and marks the version FAILED
# with a clear message instead of crashing the worker.

import mailbox
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.ingestion.parsers._email_common import elements_from_email_message
from app.ingestion.parsers.base import ParsedElement, Parser


class PstParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        if shutil.which("readpst") is None:
            raise RuntimeError(
                "readpst is not installed (brew install libpst / apt install pst-utils) — "
                "required to parse .pst files"
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            pst_path = Path(tmp_dir) / "mailbox.pst"
            pst_path.write_bytes(file.read())
            output_dir = Path(tmp_dir) / "out"
            output_dir.mkdir()

            subprocess.run(
                ["readpst", "-o", str(output_dir), "-q", str(pst_path)],
                check=True,
                capture_output=True,
                timeout=300,
            )

            elements: list[ParsedElement] = []
            for mbox_file in sorted(output_dir.rglob("*")):
                if not mbox_file.is_file():
                    continue
                elements.extend(self._elements_from_mbox_file(mbox_file))
            return elements

    def _elements_from_mbox_file(self, mbox_path: Path) -> list[ParsedElement]:
        folder_name = mbox_path.name
        box = mailbox.mbox(str(mbox_path))
        try:
            elements = []
            for index, message in enumerate(box):
                elements.extend(
                    elements_from_email_message(
                        message, extra_metadata={"folder": folder_name, "message_index": index}
                    )
                )
            return elements
        finally:
            box.close()
