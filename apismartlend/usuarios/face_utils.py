import base64
import binascii
import json

import numpy as np
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from insightface.app import FaceAnalysis
from PIL import Image, UnidentifiedImageError


class FaceProcessor:
    def __init__(self):
        self.cipher = Fernet(settings.FACE_ENCRYPTION_KEY.encode())
        providers = getattr(
            settings,
            'INSIGHTFACE_PROVIDERS',
            ['CPUExecutionProvider'],
        )
        det_size = getattr(settings, 'INSIGHTFACE_DET_SIZE', (640, 640))
        model_name = getattr(settings, 'INSIGHTFACE_MODEL', 'buffalo_l')
        self.match_threshold = getattr(settings, 'FACE_MATCH_THRESHOLD', 0.35)
        self.app = FaceAnalysis(name=model_name, providers=providers)
        self.app.prepare(ctx_id=0, det_size=det_size)

    def _load_image(self, file_obj):
        try:
            pil_image = Image.open(file_obj).convert('RGB')
        except UnidentifiedImageError:
            return None
        return np.asarray(pil_image)

    def extract_embedding(self, file_obj):
        image = self._load_image(file_obj)
        if image is None:
            return 'invalid'

        # InsightFace espera BGR.
        bgr = image[:, :, ::-1]
        faces = self.app.get(bgr)
        if not faces:
            return None

        embedding = faces[0].normed_embedding
        return np.asarray(embedding)

    def encrypt_embedding(self, embedding):
        data = json.dumps(embedding.tolist()).encode()
        token = self.cipher.encrypt(data)
        return base64.b64encode(token).decode()

    def decrypt_embedding(self, encrypted_embedding):
        if not encrypted_embedding:
            return None
        try:
            token = base64.b64decode(encrypted_embedding)
            data = self.cipher.decrypt(token)
            values = json.loads(data.decode())
        except (binascii.Error, InvalidToken, json.JSONDecodeError, AttributeError):
            return None
        return np.asarray(values, dtype=np.float32)

    def match_embeddings(self, candidate, stored, threshold=None):
        if candidate is None or stored is None:
            return False, None
        threshold = threshold if threshold is not None else self.match_threshold
        distance = float(np.linalg.norm(candidate - stored))
        return distance <= threshold, distance
