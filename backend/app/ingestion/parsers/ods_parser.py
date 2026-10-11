# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Same header=value, row-numbered shape as XlsxParser/CsvParser, one
# element per sheet (table). odfpy doesn't compute/re-expose formulas the
# way openpyxl does for XLSX, so — unlike XLSX — formulas aren't captured
# here; ODS support is value-only.

from typing import BinaryIO

from odf import teletype
from odf.opendocument import load
from odf.table import Table, TableCell, TableRow

from app.ingestion.parsers.base import ParsedElement, Parser


def _cell_text(cell) -> str:
    text = teletype.extractText(cell).strip()
    if text:
        return text
    # A cell built programmatically (or unusually exported) can carry its
    # value in an attribute with no <text:p> child at all.
    for attribute in ("value", "string-value", "date-value", "boolean-value"):
        value = cell.getAttribute(attribute)
        if value:
            return value
    return ""


class OdsParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        document = load(file)

        elements: list[ParsedElement] = []
        for table in document.spreadsheet.getElementsByType(Table):
            element = self._table_element(table)
            if element is not None:
                elements.append(element)
        return elements

    def _table_element(self, table) -> ParsedElement | None:
        rows = table.getElementsByType(TableRow)
        if not rows:
            return None

        headers = [_cell_text(cell) for cell in rows[0].getElementsByType(TableCell)]

        lines = []
        for row_number, row in enumerate(rows[1:], start=2):
            cells = row.getElementsByType(TableCell)
            pieces = []
            for index, cell in enumerate(cells):
                value = _cell_text(cell)
                if not value:
                    continue
                header = headers[index] if index < len(headers) else ""
                pieces.append(f"{header}={value}" if header else value)
            if pieces:
                lines.append(f"Row {row_number}: " + ", ".join(pieces))

        if not lines:
            return None

        sheet_name = table.getAttribute("name") or "Sheet"
        content = f"# {sheet_name}\n" + "\n".join(lines)
        return ParsedElement(content=content, metadata={"sheet": sheet_name, "headers": headers})
