# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Legacy binary Excel (97-2003). Same header=value, row-numbered shape as
# XlsxParser — xlrd is a values-only reader for this format, so unlike
# XLSX there's no formula capture here.

from typing import BinaryIO

import xlrd

from app.ingestion.parsers.base import ParsedElement, Parser


class XlsParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        workbook = xlrd.open_workbook(file_contents=file.read())

        elements: list[ParsedElement] = []
        for sheet in workbook.sheets():
            element = self._sheet_element(sheet)
            if element is not None:
                elements.append(element)
        return elements

    def _sheet_element(self, sheet) -> ParsedElement | None:
        if sheet.nrows == 0:
            return None

        headers = [str(value) for value in sheet.row_values(0)]
        lines = []
        for row_index in range(1, sheet.nrows):
            row_number = row_index + 1
            values = sheet.row_values(row_index)
            pieces = [
                f"{headers[i]}={value}" if i < len(headers) else str(value)
                for i, value in enumerate(values)
                if value not in ("", None)
            ]
            if pieces:
                lines.append(f"Row {row_number}: " + ", ".join(pieces))

        if not lines:
            return None

        content = f"# {sheet.name}\n" + "\n".join(lines)
        return ParsedElement(content=content, metadata={"sheet": sheet.name, "headers": headers})
