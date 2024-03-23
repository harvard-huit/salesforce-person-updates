from common import logger
import requests


class PersonReference():
    def __init__(self, apikey, environment="dev"):
        if apikey == None:
            raise Exception("Error: apikey required")

        self.host=""
        if environment == "prod":
            self.host="go.prod.apis.huit.harvard.edu"
        elif environment == "dev":
            self.host="go.dev.apis.huit.harvard.edu"
        elif environment == "stage":
            self.host="go.stage.apis.huit.harvard.edu"
        elif environment == "testing":
            self.host="go.testing.apis.huit.harvard.edu"
        else:
            raise ValueError(f"Error: unknown environment ({environment}). Possible values are defaulting to prod")

        self.apikey = apikey
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": apikey
        }

    def healthCheck(self):
        health_url = f"https://{ self.host }/ats/person/reference/v1/health"
        try:
            response = requests.get(health_url, headers=self.headers)
            if(response.status_code != 200):
                raise Exception(f"Error: Failure to connect to Reference API ({response.status_code})")

            return response.text

        except Exception as e:
            logger.error(f"Failure to connect to Reference API: {e}")
            raise e

    def getSchools(self):
        school_url = f"https://{ self.host }/ats/person/reference/v1/studentSchool"

        try:
            response = requests.get(school_url, headers=self.headers)
            if(response.status_code != 200):
                raise Exception("Error: failure with response from Reference API")
            
            if not "results" in response.json():
                logger.error(f"Error: Reference API gave unknown response: {response.text}")

            return response.json()

        except Exception as e:
            logger.error(f"Error: {e}")
            raise e
        
