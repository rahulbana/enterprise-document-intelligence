# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Full structural extraction, not flat text: every element is tagged with
# its slide number and the slide layout's name (e.g. "Title and Content"),
# plus a "kind" (title/textbox/table/notes/image/chart) so a citation can
# eventually say "slide 3, table" instead of just "this document". Text
# boxes carry any hyperlink URLs found in their runs. Images/charts don't
# get their pixel content read (that's a separate OCR/data-extraction
# concern) but are represented as a placeholder element carrying position
# and (for images) alt text / (for charts) title+series, so their presence
# and location are still retrievable.

from typing import Any, BinaryIO

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.ingestion.parsers.base import ParsedElement, Parser


class PptxParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        presentation = Presentation(file)
        elements: list[ParsedElement] = []

        for slide_index, slide in enumerate(presentation.slides):
            slide_number = slide_index + 1
            layout_name = slide.slide_layout.name

            def base_metadata(
                kind: str, *, _slide=slide_number, _layout=layout_name, **extra: Any
            ) -> dict[str, Any]:
                return {"slide": _slide, "slide_layout": _layout, "kind": kind, **extra}

            title_shape = slide.shapes.title
            title_shape_id = title_shape.shape_id if title_shape is not None else None
            for shape in slide.shapes:
                if shape.shape_id == title_shape_id:
                    if shape.has_text_frame and shape.text_frame.text.strip():
                        elements.append(
                            ParsedElement(
                                content=shape.text_frame.text, metadata=base_metadata("title")
                            )
                        )
                    continue

                if shape.has_table:
                    rows = [" | ".join(cell.text for cell in row.cells) for row in shape.table.rows]
                    content = "\n".join(rows)
                    if content.strip():
                        table_metadata = base_metadata(
                            "table",
                            rows=len(shape.table.rows),
                            columns=len(shape.table.columns),
                        )
                        elements.append(ParsedElement(content=content, metadata=table_metadata))
                elif shape.has_text_frame and shape.text_frame.text.strip():
                    hyperlinks = self._hyperlinks_in(shape.text_frame)
                    metadata = base_metadata("textbox", position=self._position(shape))
                    if hyperlinks:
                        metadata["hyperlinks"] = hyperlinks
                    elements.append(ParsedElement(content=shape.text_frame.text, metadata=metadata))
                elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    alt_text = getattr(shape, "name", "") or "image"
                    elements.append(
                        ParsedElement(
                            content=f"[Image: {alt_text}]",
                            metadata=base_metadata("image", position=self._position(shape)),
                        )
                    )
                elif shape.has_chart:
                    elements.append(
                        ParsedElement(
                            content=self._chart_summary(shape),
                            metadata=base_metadata("chart", position=self._position(shape)),
                        )
                    )

            if slide.has_notes_slide:
                notes_text = slide.notes_slide.notes_text_frame.text
                if notes_text.strip():
                    notes_metadata = base_metadata("notes")
                    elements.append(ParsedElement(content=notes_text, metadata=notes_metadata))

        return elements

    @staticmethod
    def _position(shape: Any) -> dict[str, int]:
        return {
            "left": shape.left or 0,
            "top": shape.top or 0,
            "width": shape.width or 0,
            "height": shape.height or 0,
        }

    @staticmethod
    def _hyperlinks_in(text_frame: Any) -> list[str]:
        urls = []
        for paragraph in text_frame.paragraphs:
            for run in paragraph.runs:
                address = run.hyperlink.address
                if address:
                    urls.append(address)
        return urls

    @staticmethod
    def _chart_summary(shape: Any) -> str:
        # Chart XML structure varies enough across chart types that a fully
        # robust extraction isn't worth it here — best-effort title +
        # series names, falling back to a generic placeholder.
        try:
            chart = shape.chart
            pieces = [f"[Chart: {chart.chart_type}]"]
            if chart.has_title and chart.chart_title.text_frame.text.strip():
                pieces.append(chart.chart_title.text_frame.text)
            for series in chart.series:
                if series.name:
                    pieces.append(series.name)
            return " ".join(pieces)
        except Exception:
            return "[Chart]"
