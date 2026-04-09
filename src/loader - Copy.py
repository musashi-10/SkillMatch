import pandas as pd
import logging

from .logging_file import get_log

logger = get_log()

def get_data(file):
    
    try:
        data = pd.read_csv(file)
        
        data = data.dropna()
        logger.info("Data loaded successfully.")
        return data
       
    
       
    except  Exception as e:
        logger.error(f"Error reading file: {e}")
        return None
   