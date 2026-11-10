import base64
import hashlib
import json
import os
import re

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import firebase_admin
from firebase_admin import credentials, db

firebase_json = os.environ.get('FIREBASE_CONFIG')
database_url = os.environ.get('DATABASE_URL')
aes_key_str = os.environ.get('AES_KEY')

if not firebase_admin._apps:
    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {'databaseURL': database_url})


def encrypt_data(plain_text, secret_key):
    key = hashlib.sha256(secret_key.encode('utf-8')).digest()
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(plain_text.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return base64.b64encode(iv + encrypted).decode('utf-8')


def save_encrypted_file(filename, raw_content, secret_key):
    if raw_content is None:
        raw_content = [] if filename == 'sports.json' else {}

    json_str = json.dumps(raw_content, ensure_ascii=False)
    encrypted_str = encrypt_data(json_str, secret_key)

    payload = {
        "data": encrypted_str
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)

    print(f"Success: {filename} created")


def process_events_data(events_data):
    if not isinstance(events_data, dict):
        return events_data

    if 'events' in events_data and isinstance(events_data['events'], list):
        new_events_list = []
        for ev in events_data['events']:
            if not isinstance(ev, dict):
                continue

            new_ev = {}
            new_ev['id'] = ev.get('id')
            new_ev['title'] = ev.get('title')

            if 'league_logo' in ev:
                new_ev['image'] = ev.get('league_logo')
            else:
                new_ev['image'] = ev.get('image', '')

            new_ev['cat'] = ev.get('cat', '')

            e_info = ev.get('eventInfo', {})
            new_ev['eventInfo'] = {
                'teamA': e_info.get('teamA', ''),
                'teamB': e_info.get('teamB', ''),
                'teamAFlag': e_info.get('teamAFlag', ''),
                'teamBFlag': e_info.get('teamBFlag', ''),
                'eventName': e_info.get('eventName', ''),
                'isHot': e_info.get('isHot', ''),
                'Status': e_info.get('Status', ''),
                'startTime': e_info.get('startTime', ''),
                'endTime': e_info.get('endTime', '')
            }

            old_channels = ev.get('channels_data', [])
            new_channels = []
            for ch in old_channels:
                if not isinstance(ch, dict):
                    continue

                new_ch = {}
                new_ch['title'] = ch.get('title', '')

                raw_link = ch.get('link', '')
                clean_link = raw_link
                api_val = ch.get('api', '')

                if '<iframe' in raw_link and 'src=' in raw_link:
                    src_match = re.search(r'src="([^"]+)"', raw_link)
                    if src_match:
                        src_url = src_match.group(1)
                        if '?play=' in src_url:
                            play_val = src_url.split('?play=', 1)[1]

                            if '?url=' in play_val:
                                play_val = play_val.split('?url=', 1)[1]

                            if '&k1=' in play_val and '&k2=' in play_val:
                                link_part, keys_part = play_val.split('&k1=', 1)
                                clean_link = link_part
                                k1 = ""
                                k2 = ""
                                if '&k2=' in keys_part:
                                    k1, k2_part = keys_part.split('&k2=', 1)
                                    k2 = k2_part.split('&')[0]
                                api_val = f"{k1}:{k2}"
                            else:
                                clean_link = play_val

                new_ch['link'] = clean_link
                new_ch['logo'] = ""
                new_ch['type'] = 0
                new_ch['api'] = api_val
                new_ch['tokenApi'] = ch.get('tokenApi', '')

                new_channels.append(new_ch)

            new_ev['channels_data'] = new_channels
            new_events_list.append(new_ev)

        events_data['events'] = new_events_list

    return events_data


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

    sports_data = all_data.get('SPORTS')
    extracted_sports = []

    if isinstance(sports_data, dict) and 'categories' in sports_data:
        for category in sports_data['categories']:
            if isinstance(category, dict) and 'channels_data' in category:
                extracted_sports.extend(category['channels_data'])
    elif isinstance(sports_data, dict) and 'channels_data' in sports_data:
        extracted_sports.extend(sports_data['channels_data'])
    elif isinstance(sports_data, list):
        extracted_sports = sports_data
    else:
        extracted_sports = sports_data

    save_encrypted_file('sports.json', extracted_sports, aes_key_str)

    vip_data = all_data.get('VIP_channel')
    save_encrypted_file('vip.json', vip_data, aes_key_str)

    events_data = all_data.get('sports_live')
    processed_events_data = process_events_data(events_data)
    save_encrypted_file('events.json', processed_events_data, aes_key_str)


if __name__ == '__main__':
    fetch_and_save()
