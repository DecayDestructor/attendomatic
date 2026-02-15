import requests

url = "https://attendomatic.onrender.com/adapters/telegram/webhook"
payload = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {
            "id": 1234567890,
            "is_bot": False,
            "first_name": "Test",
            "username": "test_user",
        },
        "chat": {
            "id": 1234567890,
            "first_name": "Test",
            "username": "test_user",
            "type": "private",
        },
        "date": 1730200000,
        "text": "Hello bot!",
    },
}

response = requests.post(url, json=payload)
print(response.status_code, response.text)
