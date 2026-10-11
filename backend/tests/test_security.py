# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from app.core.security import hash_password, verify_password


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password("wrong-password", hashed) is False


def test_hash_password_is_salted() -> None:
    first = hash_password("same-password")
    second = hash_password("same-password")

    assert first != second
    assert verify_password("same-password", first) is True
    assert verify_password("same-password", second) is True
