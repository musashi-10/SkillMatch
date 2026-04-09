import string
import nltk

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

import pandas as pd
from .logging_file import get_log
logger = get_log()





def clean_data(data):
    # 1. Select the specific column
    try:
        skills_column = data["skills"]
        return skills_column
    except KeyError:
        logger.error("Column 'skills' not found in the DataFrame.")
        return None
    finally:
        logger.info("Column selection done")
    
def remove_punctuation(skills_column):
        

    # 2. Use .apply with a lambda to clean each row individually
    # This prevents the recursion error and keeps your 1,000 rows separate
  cleaned_series = skills_column.apply(lambda x: " ".join([w for w in str(x).split() if w not in string.punctuation]))
    
  logger.info("Cleaning 1 done")        

  
  return cleaned_series



# 4. Return as a list of strings (one string per row)
# return cleaned_series.tolist()
from nltk.corpus import stopwords

def clean_data1(data_list):
   
   
    
    # 2. Define the stop words once (faster)
    stop_words = set(stopwords.words('english'))
    
    # 3. Use lambda to clean each row individually
    # This prevents your rows from being smashed into one giant string
    cleaned_series = data_list.apply(lambda x: " ".join([w for w in str(x).split() if w not in stop_words]))
    
    logger.info("Cleaning 2 done")        

    
    return cleaned_series



from nltk.tokenize import word_tokenize
import pandas as pd

def clean_data2(data_list):
    # 1. Convert to Series to process row-by-row

    
    def tokenize_row(text):
        try:
            # Tokenize and then JOIN back into a single string
            tokens = word_tokenize(str(text))
            return " ".join(tokens)
        except Exception as e:
            logger.error(f"Error tokenizing row: {e}")
            return str(text) # Fallback to original text if error

    # 2. Use .apply to keep your 1,000 rows separate
    cleaned_series = data_list.apply(tokenize_row)
    
    logger.info("Cleaning 3 done")
    return cleaned_series.tolist()

        
       
    