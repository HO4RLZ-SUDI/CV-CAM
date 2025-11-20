import math
from pathlib import Path
from typing import Dict, Tuple

import face_recognition
import numpy as np


def _validate_image(image_array: np.ndarray) -> None:
    if image_array.dtype != np.uint8:
        raise ValueError("Image must be 8-bit per channel (uint8).")
    if image_array.ndim != 3 or image_array.shape[2] != 3:
        raise ValueError("Image must be an 8-bit RGB image.")


def get_embedding(image_path: str) -> np.ndarray:
    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = face_recognition.load_image_file(str(image_file))
    _validate_image(image)

    face_locations = face_recognition.face_locations(image)
    if not face_locations:
        raise ValueError("No face detected in the provided image.")

    encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
    if not encodings:
        raise ValueError("Failed to compute embedding for the face.")

    return np.asarray(encodings[0], dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return -1.0
    return float(np.dot(a, b) / denom)


def recognize_image(image_path: str, face_db: Dict[str, np.ndarray], tolerance: float = 0.55) -> Tuple[str, float]:
    if not face_db:
        raise ValueError("Face database is empty.")

    probe_embedding = get_embedding(image_path)

    best_id = ""
    best_score = -1.0
    for user_id, embedding in face_db.items():
        score = _cosine_similarity(probe_embedding, np.asarray(embedding, dtype=np.float32))
        if score > best_score:
            best_score = score
            best_id = user_id

    if best_score < tolerance:
        raise ValueError("No matching face found within tolerance.")

    return best_id, best_score
