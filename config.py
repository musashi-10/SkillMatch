import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

model_path = os.path.join(BASE_DIR, "model", "model.pkl")
vectorizer_path = os.path.join(BASE_DIR, "utils", "vector.pkl")
label_encoder_path = os.path.join(BASE_DIR, "utils", "label_encoder.pkl")
file_path = os.path.join(BASE_DIR, "data", "data.csv")
file_to_save = os.path.join(BASE_DIR, "data", "new_data", "predicted_jobs.csv")
