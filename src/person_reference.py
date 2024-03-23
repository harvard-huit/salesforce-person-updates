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
            self.host="not_real_url.com"
        else:
            raise ValueError(f"Error: unknown environment ({environment}). Possible values are defaulting to prod")

        self.apikey = apikey
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": apikey
        }

        if environment != "testing":
            try:
                self.healthCheck()
            except Exception as e:
                logger.error(f"Error: Unable to connect to Person Reference API {e}")
                raise e
            
        # set up urls
        self.health_url = f"https://{ self.host }/ats/person/reference/v1/monitor/health"

        self.schools_url = f"https://{ self.host }/ats/person/reference/v1/studentSchool"
        self.units_url = f"https://{ self.host }/ats/person/reference/v1/academicUnit"
        self.departments_url = f"https://{ self.host }/ats/person/reference/v1/department"
        self.sub_affiliations_url = f"https://{ self.host }/ats/person/reference/v1/subAffiliation"
        self.major_affiliations_url = f"https://{ self.host }/ats/person/reference/v1/majorAffiliation"

    def healthCheck(self):
        return self.getResultsText(self.health_url)
    
    def getSchools(self):
        return self.getResultsJson(self.schools_url)

    def getUnits(self):
        return self.getResultsJson(self.units_url) 

    def getDepartments(self):
        return self.getResultsJson(self.departments_url)

    def getSubAffiliations(self):
        return self.getResultsJson(self.sub_affiliations_url)

    def getMajorAffiliations(self):
        return self.getResultsJson(self.major_affiliations_url)
    
    def getMajAffiliations(self):
        logger.warning("Warning: why are you using this? Please use getMajorAffiliations instead. getMajAffiliations will not be removed ever, I just want to shame you for not using the right method.")
        return self.getResults(self.major_affiliations_url)

    def getResultsJson(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            if(response.status_code != 200):
                raise Exception("Error: failure with response from Reference API")
            
            if not "results" in response.json():
                logger.error(f"Error: Reference API gave unknown response: {response.text}")

            return response.json()

        except Exception as e:
            logger.error(f"Error: {e}")
            raise e
        
    def getResultsText(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            if(response.status_code != 200):
                raise Exception("Error: failure with response from Reference API")
            
            return response.text

        except Exception as e:
            logger.error(f"Error: {e}")
            raise e