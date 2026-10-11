# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# One element per top-level child of the root element (its full text
# content, tags stripped), tagged with its element path — good enough
# structure-awareness without building a full tree-to-text renderer. A
# flat/attribute-only document with no children falls back to one element
# for the whole root.

from typing import BinaryIO
from xml.etree import ElementTree

from app.ingestion.parsers.base import ParsedElement, Parser


class XmlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        root = ElementTree.fromstring(file.read())

        children = list(root)
        if not children:
            text = " ".join(root.itertext()).strip()
            return [ParsedElement(content=text, metadata={"path": f"/{root.tag}"})] if text else []

        elements = []
        for index, child in enumerate(children):
            text = " ".join(child.itertext()).strip()
            if text:
                elements.append(
                    ParsedElement(
                        content=text, metadata={"path": f"/{root.tag}/{child.tag}", "index": index}
                    )
                )
        return elements
