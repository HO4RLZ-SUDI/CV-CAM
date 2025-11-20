from datetime import datetime
import json
import os
import pickle
from pathlib import Path
from typing import Dict, List

import cv2
from flask import Flask, Response, jsonify, render_template, request
import numpy as np
import serial
from werkzeug.utils import secure_filename

from face_engine import get_embedding, recognize_image

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMP_FACE_DIR = DATA_DIR / "temp_faces"
FACE_DB_PATH = DATA_DIR / "face_database.pkl"
USERS_PATH = DATA_DIR / "users.json"
STOCK_PATH = DATA_DIR / "medicine_stock.json"
ORDERS_PATH = DATA_DIR / "orders.json"


class SerialController:
    def __init__(self, port: str = os.environ.get("DISPENSER_PORT", "/dev/ttyUSB0"), baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self._connect()

    def _connect(self) -> None:
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
        except serial.SerialException:
            self.serial = None

    @property
    def available(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def trigger(self, code: str) -> bool:
        if not self.available:
            return False
        self.serial.write(code.encode("utf-8"))
        self.serial.flush()
        return True


def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    TEMP_FACE_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        USERS_PATH.write_text("[]", encoding="utf-8")
    if not STOCK_PATH.exists():
        STOCK_PATH.write_text("{}", encoding="utf-8")
    if not ORDERS_PATH.exists():
        ORDERS_PATH.write_text("[]", encoding="utf-8")
    if not FACE_DB_PATH.exists():
        FACE_DB_PATH.write_bytes(pickle.dumps({}))


def load_users() -> List[Dict]:
    return json.loads(USERS_PATH.read_text(encoding="utf-8"))


def save_users(users: List[Dict]) -> None:
    USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


def load_face_db() -> Dict[str, np.ndarray]:
    return pickle.loads(FACE_DB_PATH.read_bytes())


def save_face_db(face_db: Dict[str, np.ndarray]) -> None:
    FACE_DB_PATH.write_bytes(pickle.dumps(face_db))


def load_stock() -> Dict:
    return json.loads(STOCK_PATH.read_text(encoding="utf-8"))


def save_stock(stock: Dict) -> None:
    STOCK_PATH.write_text(json.dumps(stock, indent=2), encoding="utf-8")


def load_orders() -> List[Dict]:
    return json.loads(ORDERS_PATH.read_text(encoding="utf-8"))


def save_orders(orders: List[Dict]) -> None:
    ORDERS_PATH.write_text(json.dumps(orders, indent=2), encoding="utf-8")


app = Flask(__name__)
ensure_data_files()
serial_controller = SerialController()
camera = cv2.VideoCapture(0)


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Camera Unavailable", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            frame = blank
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/register', methods=['POST'])
def api_register():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    medicine = request.form.get('medicine', '').strip()
    image_file = request.files.get('face')

    if not name or not email or not image_file:
        return jsonify({"error": "Name, email, and face image are required."}), 400

    filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{image_file.filename}")
    image_path = TEMP_FACE_DIR / filename
    image_file.save(image_path)

    users = load_users()
    user_id = f"user_{len(users)+1}"

    face_db = load_face_db()
    try:
        embedding = get_embedding(str(image_path))
    except Exception as exc:  # noqa: BLE001
        image_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400

    face_db[user_id] = embedding
    save_face_db(face_db)

    user_record = {
        "id": user_id,
        "name": name,
        "email": email,
        "preferred_medicine": medicine,
        "registered_at": datetime.utcnow().isoformat()
    }
    users.append(user_record)
    save_users(users)

    return jsonify({"message": "User registered", "user": user_record})


@app.route('/api/scan', methods=['POST'])
def api_scan():
    image_file = request.files.get('face')
    if not image_file:
        return jsonify({"error": "Face image is required."}), 400

    filename = secure_filename(f"scan_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.jpg")
    image_path = TEMP_FACE_DIR / filename
    image_file.save(image_path)

    face_db = load_face_db()
    try:
        user_id, score = recognize_image(str(image_path), face_db, tolerance=0.55)
    except Exception as exc:  # noqa: BLE001
        image_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400

    users = load_users()
    user_data = next((u for u in users if u['id'] == user_id), None)
    image_path.unlink(missing_ok=True)

    return jsonify({"user": user_data, "score": score})


@app.route('/api/order', methods=['POST'])
def api_order():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get('user_id')
    medicine = payload.get('medicine')
    quantity = int(payload.get('quantity', 1))

    if not user_id or not medicine:
        return jsonify({"error": "user_id and medicine are required."}), 400

    stock = load_stock()
    if medicine not in stock:
        return jsonify({"error": "Medicine not found."}), 400

    if stock[medicine]['quantity'] < quantity:
        return jsonify({"error": "Insufficient stock."}), 400

    stock[medicine]['quantity'] -= quantity
    save_stock(stock)

    orders = load_orders()
    order_record = {
        "user_id": user_id,
        "medicine": medicine,
        "quantity": quantity,
        "ordered_at": datetime.utcnow().isoformat()
    }
    orders.append(order_record)
    save_orders(orders)

    dispense_code = stock[medicine].get('dispense_code')
    dispatched = False
    if dispense_code:
        dispatched = serial_controller.trigger(dispense_code)

    return jsonify({"message": "Order placed", "order": order_record, "dispensed": dispatched})


@app.route('/api/dashboard')
def api_dashboard():
    users = load_users()
    stock = load_stock()
    orders = load_orders()
    return jsonify({
        "users": users,
        "stock": stock,
        "orders": orders,
        "serial_connected": serial_controller.available
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
