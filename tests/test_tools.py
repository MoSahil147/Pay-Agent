from unittest.mock import patch, MagicMock
from state import CardData
from tools import lookup_account, process_payment


def make_mock_response(json_data: dict, status_code: int):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    return mock


def test_lookup_account_success():
    expected = {
        "account_id": "ACC1001", "full_name": "Nithin Jain",
        "dob": "1990-05-14", "aadhaar_last4": "4321",
        "pincode": "400001", "balance": 1250.75
    }
    with patch("tools._client.post", return_value=make_mock_response(expected, 200)) as mock_post:
        data, status = lookup_account("ACC1001")
        assert status == 200
        assert data["full_name"] == "Nithin Jain"
        mock_post.assert_called_once()
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["account_id"] == "ACC1001"


def test_lookup_account_not_found():
    with patch("tools._client.post", return_value=make_mock_response({"error_code": "account_not_found"}, 404)):
        data, status = lookup_account("ACC9999")
        assert status == 404
        assert data["error_code"] == "account_not_found"


def test_process_payment_success():
    card = CardData(
        cardholder_name="Nithin Jain",
        card_number="4532015112830366",
        cvv="123",
        expiry_month=12,
        expiry_year=2027
    )
    response = {"success": True, "transaction_id": "txn_123"}
    with patch("tools._client.post", return_value=make_mock_response(response, 200)) as mock_post:
        data, status = process_payment("ACC1001", 500.00, card)
        assert status == 200
        assert data["success"] is True
        payload = mock_post.call_args.kwargs["json"]
        assert payload["amount"] == 500.00
        assert payload["payment_method"]["card"]["card_number"] == "4532015112830366"


def test_process_payment_invalid_card():
    card = CardData(
        cardholder_name="Nithin Jain",
        card_number="1234567890123456",
        cvv="123",
        expiry_month=12,
        expiry_year=2027
    )
    response = {"success": False, "error_code": "invalid_card"}
    with patch("tools._client.post", return_value=make_mock_response(response, 422)):
        data, status = process_payment("ACC1001", 500.00, card)
        assert status == 422
        assert data["error_code"] == "invalid_card"
