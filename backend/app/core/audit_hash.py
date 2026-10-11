# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Pure hash-chain math for the auth audit log, kept separate from the
# service/repository so the exact byte-for-byte digest computation is
# trivial to unit test without a DB.

import hashlib
from datetime import datetime

_FIELD_SEPARATOR = "|"


def compute_entry_hash(
    *,
    prev_hash: str | None,
    created_at: datetime,
    event_type: str,
    email: str,
    user_id: int | None,
    detail: str | None,
) -> str:
    # SQLite's DateTime(timezone=True) doesn't actually preserve tzinfo — a
    # value written tz-aware comes back naive on the next read (verified:
    # datetime.now(UTC) round-trips with tzinfo=None). Stripping tzinfo here
    # before hashing means the digest computed at write time (tz-aware) and
    # at verify time (naive, post-round-trip) match; every created_at this
    # app writes is UTC by convention regardless of tzinfo presence, so this
    # loses no information, only the redundant "+00:00" suffix.
    naive_created_at = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
    payload = _FIELD_SEPARATOR.join(
        [
            prev_hash or "",
            naive_created_at.isoformat(),
            event_type,
            email,
            str(user_id) if user_id is not None else "",
            detail or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
