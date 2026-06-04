import firebase_admin
from firebase_admin import credentials, messaging

cred = credentials.Certificate("google_firebase_credentials.json")
firebase_admin.initialize_app(cred)

def send_push_notification(device_token: str, title: str, body: str):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=device_token,
    )

    response = messaging.send(message)
    print(f"Successfully sent FCM message: {response}")
