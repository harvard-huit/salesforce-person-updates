import requests
import json
from common import logger

class Departments:
    def __init__(self, apikey):
        if apikey == None:
            raise Exception("Error: apikey required")

        self.apikey = apikey
        self.results = []
        self.count = 0
        self.total_count = 0
        try: 
            self.results = self.getDepartments(apikey=self.apikey)
            # self.__setattr__('response', self.response)
            # self.count = self.response['count']
            # self.__setattr__('count', self.count)w
        except Exception as e:
            logger.error(f"Error getting valid data from Departments API: {e}")
            raise e

        self.departments = self.hashSort(self.results)

    def __str__(self):
        return str(self.results)
    def __repr__(self):
        return str(self.results)

    def getDepartments(self, apikey):
        if self == None and apikey == None:
            raise Exception("Error: apikey required")

        url = "https://go.apis.huit.harvard.edu/ats/hr-departments/v2/departments"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": apikey
        }

        #calling departments api            
        response = requests.get(url, 
            headers = headers)

        # logger.debug(json.loads(response.text))
        # logger.debug(response.status_code)
        if(response.status_code != 200):
            raise Exception("Error: failure with response from Departments API")
        
        if not isinstance(response.json(), list):
            logger.error(f"Error: Deparments API gave unknown response: {response.json()}")

        return json.loads(response.text)
        
    def hashSort(self, results):
        if not isinstance(results, list):
            raise Exception(f"Error: hashSort requires a valid response from the Departments API")

        departments = {}
        for result in results:
            departments[result['hrDeptId']] = result

        return departments
    
    def get_major_affiliations(self, departments):
        if departments == None:
            raise Exception("Error: departments required")

        major_affiliations = []
        for department in departments:
            if departments[department]['majAffiliation'] not in major_affiliations:
                major_affiliations.append({
                    department['majAffiliation']['code']: department['majAffiliation']['description']
                })
        return major_affiliations
    
    def get_sub_affiliations(self, departments):
        if departments == None:
            raise Exception("Error: departments required")

        minor_affiliations = []
        for department in departments:
            if departments[department]['subAffiliation'] not in minor_affiliations:
                minor_affiliations.append({
                    department['subAffiliation']['code']: department['subAffiliation']['description']
                })
        return minor_affiliations