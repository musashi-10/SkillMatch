import pandas as pd 
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import config
import logging
import pickle

from src.cleaner import clean_data
from src.cleaner import remove_punctuation
from src.cleaner import clean_data1
from src.cleaner import clean_data2
from src.logging_file import get_log

logger = get_log()

model=pickle.load(open(config.model_path, 'rb'))
vectorizer=pickle.load(open(config.vectorizer_path, 'rb'))
label_encoder=pickle.load(open(config.label_encoder_path, 'rb'))
def integretion(text):

    if isinstance(text, list):
        text = text[0]

    text = str(text)

    df = pd.DataFrame({"skills": [text]})

    x = clean_data(df)
    x = remove_punctuation(x)
    x = clean_data1(x)
    x = clean_data2(x)

    cleaned_text = x[0]

    data_1 = vectorizer.transform([cleaned_text])

    prediction = model.predict(data_1)
    prediction = label_encoder.inverse_transform(prediction)

    return prediction[0]

    

   
    

   

