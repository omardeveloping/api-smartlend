import base64
import json

import numpy as np
from cryptography.fernet import Fernet
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
