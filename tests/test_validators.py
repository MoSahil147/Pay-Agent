from validators import luhn_check, is_amex, validate_cvv, validate_expiry, validate_amount, parse_date

def test_luhn_valid():
    assert luhn_check("4532015112830366") is True

def test_luhn_invalid():
    assert luhn_check("1234567890123456") is False

def test_luhn_strips_spaces():
    assert luhn_check("4532 0151 1283 0366") is True

def test_is_amex_true():
    assert is_amex("378282246310005") is True
    assert is_amex("371449635398431") is True

def test_is_amex_false():
    assert is_amex("4532015112830366") is False

def test_cvv_standard_3_digits():
    assert validate_cvv("123", "4532015112830366") is True

def test_cvv_standard_wrong_length():
    assert validate_cvv("12", "4532015112830366") is False
    assert validate_cvv("1234", "4532015112830366") is False

def test_cvv_amex_4_digits():
    assert validate_cvv("1234", "378282246310005") is True

def test_cvv_amex_3_digits_fails():
    assert validate_cvv("123", "378282246310005") is False

def test_validate_expiry_future():
    assert validate_expiry(12, 2027) is True

def test_validate_expiry_past():
    assert validate_expiry(1, 2020) is False

def test_validate_expiry_invalid_month():
    assert validate_expiry(13, 2027) is False
    assert validate_expiry(0, 2027) is False

def test_validate_amount_valid():
    ok, err = validate_amount(500.00, 1250.75)
    assert ok is True
    assert err == ""

def test_validate_amount_full():
    ok, err = validate_amount(1250.75, 1250.75)
    assert ok is True

def test_validate_amount_exceeds_balance():
    ok, err = validate_amount(2000.00, 1250.75)
    assert ok is False
    assert err == "insufficient_balance"

def test_validate_amount_zero():
    ok, err = validate_amount(0, 1250.75)
    assert ok is False
    assert err == "invalid_amount"

def test_validate_amount_negative():
    ok, err = validate_amount(-100, 1250.75)
    assert ok is False
    assert err == "invalid_amount"

def test_validate_amount_too_many_decimals():
    ok, err = validate_amount(100.123, 1250.75)
    assert ok is False
    assert err == "invalid_amount"

def test_parse_date_iso():
    assert parse_date("1990-05-14") == "1990-05-14"

def test_parse_date_dmy():
    assert parse_date("14-05-1990") == "1990-05-14"

def test_parse_date_natural():
    assert parse_date("14th May 1990") == "1990-05-14"

def test_parse_date_short_year():
    assert parse_date("May 14, 90") == "1990-05-14"

def test_parse_date_leap_year():
    assert parse_date("1988-02-29") == "1988-02-29"

def test_parse_date_invalid():
    assert parse_date("not a date") is None

def test_parse_date_invalid_leap():
    assert parse_date("1990-02-29") is None
