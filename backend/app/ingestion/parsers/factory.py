# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Picks a Parser by file extension. New file types register here and
# nowhere else. .doc/.ppt/.pps (legacy binary Office formats) are
# deliberately not registered — no reliable pure-Python path, and
# LibreOffice was declined as a dependency (see PLAN.md Phase 10).

from app.ingestion.parsers.base import Parser
from app.ingestion.parsers.csv_parser import CsvParser, TsvParser
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.eml_parser import EmlParser
from app.ingestion.parsers.epub_parser import EpubParser
from app.ingestion.parsers.html_parser import HtmlParser
from app.ingestion.parsers.image_parser import ImageParser
from app.ingestion.parsers.json_parser import JsonParser
from app.ingestion.parsers.jsonl_parser import JsonlParser
from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.mbox_parser import MboxParser
from app.ingestion.parsers.mhtml_parser import MhtmlParser
from app.ingestion.parsers.msg_parser import MsgParser
from app.ingestion.parsers.odp_parser import OdpParser
from app.ingestion.parsers.ods_parser import OdsParser
from app.ingestion.parsers.odt_parser import OdtParser
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.parsers.pptx_parser import PptxParser
from app.ingestion.parsers.pst_parser import PstParser
from app.ingestion.parsers.rtf_parser import RtfParser
from app.ingestion.parsers.txt_parser import TxtParser
from app.ingestion.parsers.xhtml_parser import XhtmlParser
from app.ingestion.parsers.xls_parser import XlsParser
from app.ingestion.parsers.xlsx_parser import XlsxParser
from app.ingestion.parsers.xml_parser import XmlParser
from app.ingestion.parsers.yaml_parser import YamlParser

_pptx = PptxParser()
_image = ImageParser()
_html = HtmlParser()

_PARSERS: dict[str, Parser] = {
    # Core documents
    "pdf": PdfParser(),
    "docx": DocxParser(),
    "rtf": RtfParser(),
    "odt": OdtParser(),
    "txt": TxtParser(),
    "md": MarkdownParser(),
    "markdown": MarkdownParser(),
    "htm": _html,
    "html": _html,
    "xhtml": XhtmlParser(),
    "mhtml": MhtmlParser(),
    "mht": MhtmlParser(),
    "xml": XmlParser(),
    "epub": EpubParser(),
    "json": JsonParser(),
    "yaml": YamlParser(),
    "yml": YamlParser(),
    # Presentations
    "pptx": _pptx,
    "ppsx": _pptx,  # same OOXML package format as .pptx
    "odp": OdpParser(),
    # Spreadsheets
    "xlsx": XlsxParser(),
    "xlsm": XlsxParser(),  # same OOXML format, macros aren't parsed as text
    "xls": XlsParser(),
    "csv": CsvParser(),
    "tsv": TsvParser(),
    "ods": OdsParser(),
    "jsonl": JsonlParser(),
    # Images (OCR)
    "png": _image,
    "jpg": _image,
    "jpeg": _image,
    "tif": _image,
    "tiff": _image,
    "bmp": _image,
    "webp": _image,
    "gif": _image,
    "heic": _image,
    # Email
    "eml": EmlParser(),
    "msg": MsgParser(),
    "mbox": MboxParser(),
    "pst": PstParser(),
}


def get_parser(file_type: str) -> Parser:
    parser = _PARSERS.get(file_type)
    if parser is None:
        valid = ", ".join(sorted(_PARSERS))
        raise ValueError(f"No parser registered for file type '{file_type}'. Valid: {valid}")
    return parser
