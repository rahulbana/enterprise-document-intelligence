# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# `chunk_text` re-exported here so existing imports (`from
# app.ingestion.chunking import chunk_text`) keep working now that this is a
# package rather than a single module.

from app.ingestion.chunking.word_packing import chunk_text

__all__ = ["chunk_text"]
