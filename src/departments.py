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

        self.department_hash = self.hashSort(self.results)

        self.known_postfixes = ['', 'MA', 'SA']
        self.known_prefixes = ['', 'CS', 'EVP', 'FAS', 'HBS', 'HG', 'HL', 'HLS', 'HMS', 'HUCTW', 'HUIT', 'HUPD', 'KSG', 'LAW', 'UNION', 'VPA', 'VPD', 'VPF', 'VPG']


    def __str__(self):
        return str(self.results)
    def __repr__(self):
        return str(self.results)
    
    def simplify_code(self, code):
        postfix = ''
        if '^' in code:
            postfix = code.split('^')[-1:][0]
            code = ''.join(code.split('^')[:-1])
        
        if postfix not in self.known_postfixes:
            logger.error(f"unknown postfix: {postfix}")
            return None
        postfix_code = self.known_postfixes.index(postfix)

        prefix = ''
        if '_' in code:
            prefix = code.split('_')[0]
            code = ''.join(code.split('_')[1:])

        if prefix not in self.known_prefixes:
            logger.error(f"unknown prefix: {prefix}")
            return None
        prefix_code = self.known_prefixes.index(prefix)
        
        # trim code to be at most 7 characters
        if len(code) > 7:
            code = code[:7]

        new_code = f"{prefix_code}{code}{postfix_code}"

        if len(new_code) > 10:
            logger.error(f"Error: new code is too long: {new_code}")
            return None

        return new_code


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

        major_affiliations_map = {}
        for department_code, department in departments.items():
            if 'majAffiliation' not in department:
                continue
            if 'code' not in department['majAffiliation']:
                continue
            if department['majAffiliation']['code'] == None:
                continue
            if department['majAffiliation']['code'] not in major_affiliations_map.keys():
                major_affiliations_map[department['majAffiliation']['code']] = {
                    'description': department['majAffiliation']['description']
                }

        return major_affiliations_map
    
    def get_sub_affiliations(self, departments):
        if departments == None:
            raise Exception("Error: departments required")

        sub_affiliations_map = {}
        for department_code, department in departments.items():
            if 'subAffiliation' not in department:
                continue
            if 'code' not in department['subAffiliation']:
                continue
            if department['subAffiliation']['code'] == None:
                continue
            if department['subAffiliation']['code'] not in sub_affiliations_map.keys():
                sub_affiliations_map[department['subAffiliation']['code']] = {
                    'description': department['subAffiliation']['description'],
                    'parent_code': department['majAffiliation']['code']
                }


        return sub_affiliations_map