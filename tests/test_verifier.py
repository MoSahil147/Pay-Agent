from state import AccountData
from verifier import verify_name, verify_secondary

ACCOUNT = AccountData(
    account_id="ACC1001",
    full_name="Nithin Jain",
    dob="1990-05-14",
    aadhaar_last4="4321",
    pincode="400001",
    balance=1250.75
)

def test_verify_name_exact_match():
    assert verify_name("Nithin Jain", ACCOUNT) is True

def test_verify_name_case_sensitive():
    assert verify_name("nithin jain", ACCOUNT) is False
    assert verify_name("NITHIN JAIN", ACCOUNT) is False

def test_verify_name_strips_whitespace():
    assert verify_name("  Nithin Jain  ", ACCOUNT) is True

def test_verify_name_wrong_name():
    assert verify_name("John Doe", ACCOUNT) is False

def test_verify_secondary_dob_match():
    assert verify_secondary("dob", "1990-05-14", ACCOUNT) is True

def test_verify_secondary_dob_no_match():
    assert verify_secondary("dob", "1990-05-15", ACCOUNT) is False

def test_verify_secondary_aadhaar_match():
    assert verify_secondary("aadhaar_last4", "4321", ACCOUNT) is True

def test_verify_secondary_aadhaar_no_match():
    assert verify_secondary("aadhaar_last4", "9999", ACCOUNT) is False

def test_verify_secondary_pincode_match():
    assert verify_secondary("pincode", "400001", ACCOUNT) is True

def test_verify_secondary_pincode_no_match():
    assert verify_secondary("pincode", "400002", ACCOUNT) is False

def test_verify_secondary_unknown_factor():
    assert verify_secondary("email", "test@test.com", ACCOUNT) is False

LONG_NAME_ACCOUNT = AccountData(
    account_id="ACC1002",
    full_name="Rajarajeswari Balasubramaniam",
    dob="1985-11-23",
    aadhaar_last4="9876",
    pincode="400002",
    balance=540.00
)

def test_verify_long_name():
    assert verify_name("Rajarajeswari Balasubramaniam", LONG_NAME_ACCOUNT) is True

def test_verify_nickname_fails():
    assert verify_name("Raja", LONG_NAME_ACCOUNT) is False
