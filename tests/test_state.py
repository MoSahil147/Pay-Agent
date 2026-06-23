from state import State, AccountData, CardData, ConversationState


def test_initial_state():
    s = ConversationState()
    assert s.state == State.GREETING
    assert s.account_id is None
    assert s.account is None
    assert s.verified is False
    assert s.retry_count == 0
    assert s.name_verified is False
    assert s.payment_amount is None
    assert s.card.card_number is None
    assert s.transaction_id is None
    assert s.history == []


def test_account_data_fields():
    a = AccountData(
        account_id="ACC1001",
        full_name="Nithin Jain",
        dob="1990-05-14",
        aadhaar_last4="4321",
        pincode="400001",
        balance=1250.75
    )
    assert a.account_id == "ACC1001"
    assert a.balance == 1250.75


def test_card_data_defaults():
    c = CardData()
    assert c.card_number is None
    assert c.expiry_month is None
