import json
import os
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, send_from_directory
from flask_cors import CORS

# Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("[OK] Firebase connected")

# Flask 
app = Flask(__name__)
CORS(app)


@app.route("/")
def index():
    return open("index.html").read()


@app.route("/index.css")
def css():
    return open("index.css").read(), 200, {"Content-Type": "text/css"}

@app.route("/round_touch_app_white_36dp.png")
def icon():
    return send_from_directory("2x", "round_touch_app_white_36dp.png")


@app.route("/saveTaps", methods=["POST", "OPTIONS"])
def save_taps():

    if request.method == "OPTIONS":
        return "", 204

    print("\n--- POST received ---")
    print("id  :", request.form.get("id"))
    print("var :", request.form.get("var"))
    print("taps:", request.form.get("taps", "")[:80])

    session_id = request.form.get("id",   "")
    platform   = request.form.get("var",  "")
    taps_raw   = request.form.get("taps", "")

    if not session_id or not taps_raw:
        print("[ERROR] Missing fields")
        return "Data saved successfully"

    try:
        taps = json.loads(taps_raw)
    except Exception as e:
        print("[ERROR] Bad JSON:", e)
        return "Data saved successfully"

    try:
        batch = db.batch()
        col = db.collection("tap_logs")

        for tap in taps:
            start = int(tap.get("startTimestamp", 0))
            end   = int(tap.get("endTimestamp",   0))
            ref   = col.document()
            batch.set(ref, {
                "sessionId":         session_id,
                "platform":          platform,
                "tapSequenceNumber": int(tap.get("tapSequenceNumber", 0)),
                "startTimestamp":    start,
                "endTimestamp":      end,
                "duration":          float(end - start),
                "interfaceSequence": int(tap.get("interfaceSequence", 1)),
                "interfaceType":     str(tap.get("interface", "")),
                "ingestedAt":        datetime.now(timezone.utc),
            })

        batch.commit()
        print(f"[SUCCESS] {len(taps)} taps saved — session={session_id}")

    except Exception as e:
        print("[FIRESTORE ERROR]", e)

    return "Data saved successfully"


if __name__ == "__main__":
    print("Go to → http://localhost:5000")
    app.run(debug=False, port=5000)