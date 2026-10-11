# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# One element per sheet (or per explicitly-defined Excel Table within a
# sheet, when present), content built as one header-labeled line per row
# ("Row 2 (A2:C2): Name=Alice, Department=Engineering, Salary=120000") so
# both the header association and the row/column coordinates are visible in
# the text itself, not just in metadata. Formulas are read via a second
# pass (openpyxl can't give both the formula string and its cached result
# from one load) and kept verbatim in metadata.formulas keyed by cell
# coordinate; the content line shows the cached value when Excel has
# computed one, falling back to the formula string itself when it hasn't
# (a file that was never opened in real Excel has no cached results at all).

import io
from typing import Any, BinaryIO

import openpyxl
from openpyxl.utils import get_column_letter

from app.ingestion.parsers.base import ParsedElement, Parser


class XlsxParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        data = file.read()
        formula_workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
        value_workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True)

        elements: list[ParsedElement] = []
        for sheet_name in formula_workbook.sheetnames:
            formula_sheet = formula_workbook[sheet_name]
            value_sheet = value_workbook[sheet_name]
            element = self._sheet_element(sheet_name, formula_sheet, value_sheet)
            if element is not None:
                elements.append(element)

        return elements

    def _sheet_element(
        self, sheet_name: str, formula_sheet: Any, value_sheet: Any
    ) -> ParsedElement | None:
        rows = list(formula_sheet.iter_rows())
        if not rows:
            return None

        header_cells = rows[0]
        headers = [str(cell.value) if cell.value is not None else "" for cell in header_cells]

        lines: list[str] = []
        formulas: dict[str, str] = {}
        for row in rows[1:]:
            if all(cell.value is None for cell in row):
                continue
            row_number = row[0].row
            first_col = get_column_letter(row[0].column)
            last_col = get_column_letter(row[-1].column)

            pieces = []
            for column_index, cell in enumerate(row):
                if cell.value is None:
                    continue
                header = headers[column_index] if column_index < len(headers) else ""
                display_value = cell.value
                if cell.data_type == "f":
                    formulas[cell.coordinate] = cell.value
                    cached = value_sheet[cell.coordinate].value
                    display_value = cached if cached is not None else cell.value
                label = f"{header}={display_value}" if header else str(display_value)
                pieces.append(label)

            if pieces:
                coords = f"{first_col}{row_number}:{last_col}{row_number}"
                lines.append(f"Row {row_number} ({coords}): " + ", ".join(pieces))

        if not lines:
            return None

        content = f"# {sheet_name}\n" + "\n".join(lines)
        metadata: dict[str, Any] = {
            "sheet": sheet_name,
            "kind": "sheet",
            "range": formula_sheet.dimensions,
            "headers": headers,
        }
        if formulas:
            metadata["formulas"] = formulas
        return ParsedElement(content=content, metadata=metadata)
