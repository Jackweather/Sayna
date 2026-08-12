from pathlib import Path
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request, send_file

BASE_DIR = Path(__file__).resolve().parent
SELECTIONS_FILE = BASE_DIR / "confirmed_dates.json"
app = Flask(__name__)


def load_confirmations():
    if not SELECTIONS_FILE.exists():
        return []

    with SELECTIONS_FILE.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if isinstance(data, dict):
        return [data]

    if isinstance(data, list):
        return data

    return []


def save_confirmations(confirmations):
    with SELECTIONS_FILE.open("w", encoding="utf-8") as file_handle:
        json.dump(confirmations, file_handle, indent=2)


def latest_confirmation():
    confirmations = load_confirmations()
    if not confirmations:
        return None
    return confirmations[-1]


def confirmation_event_time(confirmation):
    if not confirmation:
        return None

    date_text = str(confirmation.get("date") or "").strip()
    if not date_text:
        return None

    for fmt in ("%A, %B %d %Y %I:%M %p", "%A, %B %d %Y"):
        try:
            if fmt.endswith("%I:%M %p"):
                time_text = str(confirmation.get("time") or "12:00 PM").strip()
                return datetime.strptime(f"{date_text} {datetime.now(timezone.utc).year} {time_text}", fmt).replace(tzinfo=timezone.utc)
            return datetime.strptime(f"{date_text} {datetime.now(timezone.utc).year}", fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def confirmation_locked(confirmation):
    if not confirmation:
        return False

    event_time = confirmation_event_time(confirmation)
    if not event_time:
        return False

    return datetime.now(timezone.utc) >= event_time - timedelta(hours=24)


@app.route("/")
def index():
    return send_file(BASE_DIR / "index.html")


@app.route("/confirm", methods=["POST"])
def confirm():
    payload = request.get_json(silent=True) or {}
    date = str(payload.get("date") or "").strip()
    time = str(payload.get("time") or "").strip()
    shop = str(payload.get("shop") or "").strip()

    if not date or not time or not shop:
        return jsonify({"error": "date, time, and coffee shop are required"}), 400

    existing = latest_confirmation()
    if confirmation_locked(existing):
        return jsonify({"error": "this confirmation is locked"}), 403

    save_confirmations([{
        "date": date,
        "time": time,
        "shop": shop,
        "confirmed_at": datetime.now(timezone.utc).isoformat()
    }])
    return jsonify({"ok": True})


@app.route("/latest-confirmation")
def get_latest_confirmation():
    confirmation = latest_confirmation()
    return jsonify({
        "confirmation": confirmation,
        "locked": confirmation_locked(confirmation),
        "server_date": datetime.now(timezone.utc).date().isoformat()
    })


@app.route("/conf")
def view_confirmations():
    confirmation = latest_confirmation()
    if not confirmation:
        items = "<li>No confirmations yet.</li>"
    else:
        status = "Locked in" if confirmation_locked(confirmation) else "Can still be changed"
        items = (
            f"<li>{confirmation['date']} at {confirmation['time']} at "
            f"{confirmation.get('shop', 'Unknown shop')} - {status}</li>"
        )

    return (
        "<!DOCTYPE html>"
        "<html lang='en'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Hidden Confirmations</title>"
        "<style>body{font-family:Segoe UI,sans-serif;background:#f6eee6;color:#2f241f;padding:2rem;}"
        ".panel{max-width:640px;margin:0 auto;background:#fff;padding:2rem;border-radius:24px;box-shadow:0 18px 40px rgba(73,44,33,.12);}"
        "h1{margin-top:0;}li{margin:.7rem 0;font-size:1.05rem;}</style></head>"
        f"<body><main class='panel'><h1>Hidden confirmations</h1><ul>{items}</ul></main></body></html>"
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
