import face_recognition

path = r"C:\Users\omarc\OneDrive\Imágenes\Neme_cropped_rgb.jpg"
image = face_recognition.load_image_file(path)
print("shape:", image.shape, "dtype:", image.dtype)
print("face_locations:", face_recognition.face_locations(image))
