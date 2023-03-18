import requests
import os
import json
from common import logger

def search(query=''):
    PDS_APIKEY = os.getenv("PDS_APIKEY")

    pdsUrl = "https://go.dev.apis.huit.harvard.edu/ats/person/v3/search"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": PDS_APIKEY
    }

    payload = query

    #calling PDS api            
    response = requests.post(pdsUrl, 
        headers = headers,
        data =  json.dumps(payload))

    logger.info(json.loads(response.text))

    return json.loads(response.text)