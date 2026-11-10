import os
import json
import base64
import hashlib
import firebase_admin
from firebase_admin import credentials, db
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

firebase_json = os.environ.get('FIREBASE_CONFIG')
database_url = os.environ.get('DATABASE_URL')
aes_key_str = os.environ.get('AES_KEY')

if not firebase_admin._apps:
    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': database_url
    })

def encrypt_data(plain_text, secret_key):
    key = hashlib.sha256(secret_key.encode('utf-8')).digest()
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(plain_text.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return base64.b64encode(iv + encrypted).decode('utf-8')

def save_encrypted_file(filename, raw_content, secret_key):
    json_str = json.dumps(raw_content if raw_content is not None else {}, ensure_ascii=False)
    encrypted_str = encrypt_data(json_str, secret_key)
    payload = {
        "data": encrypted_str
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)
    print(f"Success: {filename} created")

def fetch_and_save():
    root_ref = db.reference('/')
    all_data = root_ref.get()

    if not all_data or not isinstance(all_data, dict):
        all_data = {}

    excluded_keys = {'Highlights', 'delete_channels', 'delete_events'}
    filtered_data = {
        key: value for key, value in all_data.items()
        if key not in excluded_keys
    }
    save_encrypted_file('data.json', filtered_data, aes_key_str)

    sports_raw = all_data.get('SPORTS', {})
    sports_final = {}
    
    if isinstance(sports_raw, dict) and 'categories' in sports_raw and isinstance(sports_raw['categories'], list) and len(sports_raw['categories']) > 0:
        sports_final = {"channels_data": sports_raw['categories'][0].get('channels_data', [])}
    else:
        sports_final = sports_raw

    save_encrypted_file('sports.json', sports_final, aes_key_str)

    vip_data = all_data.get('VIP_channel')
    save_encrypted_file('vip.json', vip_data, aes_key_str)

    events_data = all_data.get('sports_live')
    save_encrypted_file('events.json', events_data, aes_key_str)

if __name__ == "__main__":
    fetch_and_save()
