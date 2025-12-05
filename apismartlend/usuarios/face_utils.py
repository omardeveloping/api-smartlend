import face_recognition
import numpy as np
import json
import base64
from cryptography.fernet import Fernet
from django.conf import settings
from PIL import Image

class FaceProcessor:
    def __init__(self):
        self.cipher = Fernet(settings.FACE_ENCRYPTION_KEY.encode())
        # Tolerancia: 0.6: Menor es más estricto.
        self.match_threshold = 0.6

    def extract_embedding(self, file_obj):
        """
        Extrae el embedding del rostro
        """
        try:
            image = face_recognition.load_image_file(file_obj)
            face_encodings = face_recognition.face_encodings(image)

            if len(face_encodings) == 0:
                print("No se encontró ningún rostro en la imagen.")
                return None
            
            if len(face_encodings) > 1:
                print("Se encontró más de un rostro. Usando el primero.")
                # Esto opcionmal por ahora pero podriamos usarlo para rechazar más rostros que se puedan ver en la imagen
                pass

            return face_encodings[0]

        except Exception as e:
            print(f"Error procesando rostro con face_recognition: {e}")
            return 'invalid'

    def encrypt_embedding(self, embedding):
        if embedding is None:
            return None
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
            return np.asarray(values)
        except Exception as e:
            print(f"Error desencriptando: {e}")
            return None

    def match_embeddings(self, candidate_encoding, stored_encoding, threshold=None):
        
        if candidate_encoding is None or stored_encoding is None:
            return False, 0.0
            
        threshold = threshold if threshold is not None else self.match_threshold
        
        # face_recognition.face_distance devuelve una lista de distancias
        # Comparamos el candidato contra una lista que contiene solo el guardado [stored]
        distances = face_recognition.face_distance([stored_encoding], candidate_encoding)
        
        distancia = distances[0]
        is_match = distancia <= threshold
        
        # Convertimos numpy bool/float a tipos nativos de Python
        return bool(is_match), float(distancia)