# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from app.core.config import settings
from app.core.jwt import TokenError, create_access_token, create_refresh_token, decode_token


def test_access_token_roundtrip() -> None:
    token = create_access_token(42)

    assert decode_token(token, expected_type="access") == 42


def test_refresh_token_roundtrip() -> None:
    token = create_refresh_token(7)

    assert decode_token(token, expected_type="refresh") == 7


def test_decode_rejects_wrong_token_type() -> None:
    access_token = create_access_token(1)

    with pytest.raises(TokenError):
        decode_token(access_token, expected_type="refresh")


def test_decode_rejects_tampered_signature() -> None:
    token = create_access_token(1)
    tampered = token[:-4] + ("0" * 4 if token[-4:] != "0000" else "1111")

    with pytest.raises(TokenError):
        decode_token(tampered, expected_type="access")


def test_decode_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": "1",
        "type": "access",
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=5),
    }
    expired_token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(TokenError):
        decode_token(expired_token, expected_type="access")
