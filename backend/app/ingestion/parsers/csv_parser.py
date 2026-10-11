# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# One element for the whole file (CSV/TSV have no sheet concept), one line
# per row labeled with the header and 1-indexed row number — same
# header=value, row-number-tagged shape as XlsxParser's rows, so a citation
# reads the same way regardless of which spreadsheet format it came from.

import csv
import io
from typing import BinaryIO

from app.ingestion.parsers.base import ParsedElement, Parser


class _DelimitedParser(Parser):
    _delimiter: str

    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        text = file.read().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text), delimiter=self._delimiter)
        rows = list(reader)
        if not rows:
            return []

        headers = rows[0]
        lines = []
        for row_number, row in enumerate(rows[1:], start=2):
            pieces = [
                f"{headers[index]}={value}" if index < len(headers) else value
                for index, value in enumerate(row)
                if value != ""
            ]
            if pieces:
                lines.append(f"Row {row_number}: " + ", ".join(pieces))

        if not lines:
            return []
        return [ParsedElement(content="\n".join(lines), metadata={"headers": headers})]


class CsvParser(_DelimitedParser):
    _delimiter = ","


class TsvParser(_DelimitedParser):
    _delimiter = "\t"
