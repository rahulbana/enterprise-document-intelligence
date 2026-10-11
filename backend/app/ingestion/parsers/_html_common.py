# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Shared "HTML soup -> heading-sectioned elements" logic for HtmlParser,
# XhtmlParser (same markup, different MIME wrapper), and MhtmlParser (MIME
# envelope around the same markup). Walks headings + block tags in document
# order (BeautifulSoup's find_all is document-order regardless of nesting)
# and groups content under whichever heading precedes it, so a citation can
# say "under 'Pricing'" instead of just "this page". A page with no headings
# at all just becomes one element.

from bs4 import BeautifulSoup

from app.ingestion.parsers.base import ParsedElement

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "td"]


def elements_from_html(html: str) -> list[ParsedElement]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all(_BLOCK_TAGS)

    if not any(block.name in _HEADING_TAGS for block in blocks):
        text = soup.get_text(separator="\n", strip=True)
        return [ParsedElement(content=text)] if text else []

    elements: list[ParsedElement] = []
    current_heading: str | None = None
    current_level: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            metadata = {"heading": current_heading, "level": current_level}
            elements.append(ParsedElement(content=content, metadata=metadata))
        buffer.clear()

    for block in blocks:
        text = block.get_text(strip=True)
        if not text:
            continue
        if block.name in _HEADING_TAGS:
            flush()
            current_heading = text
            current_level = int(block.name[1])
            buffer.append(text)
        else:
            buffer.append(text)

    flush()
    return elements
