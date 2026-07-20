import requests
from dotenv import load_dotenv
import os
from pprint import pprint

load_dotenv()

CONNECT_API_KEY = os.getenv("CONNECT_API_KEY")

url = "https://api.liteapi.travel/v3.0/hotels/rates"

headers = {
    "X-API-Key": CONNECT_API_KEY,
    "accept": "application/json",
    "Content-Type": "application/json"
}

payload = {
    "currency": "USD",
    "guestNationality": "US",
    "checkin": "2026-07-01",
    "checkout": "2026-07-02",
    "occupancies": [
        {
            "adults": 2
        }
    ],
    "hotelIds": [
        "lp1aad3"
    ]
}

r = requests.post(url, headers=headers, json=payload)

print("Status:", r.status_code)
print("Content-Type:", r.headers.get("content-type"))
print("Raw Body:", r.text[:2000])

if r.text.strip():
    pprint(r.json())
else:
    print("Empty response body")