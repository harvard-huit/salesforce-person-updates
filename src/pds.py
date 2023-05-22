import requests
import json
from common import logger
from dotmap import DotMap


class People:
    def __init__(self, apikey, batch_size=50):
        if apikey == None:
            raise Exception("Error: apikey required")

        self.apikey = apikey
        self.last_query = None
        self.response = {}
        self.results = []
        self.count = 0
        self.total_count = 0
        self.batch_size = batch_size
        self.pds_url = "https://go.apis.huit.harvard.edu/ats/person/v3/search"

        self.paginate = False
        self.session_id = None

    def __str__(self):
        return str(self.response)
    def __repr__(self):
        return str(self.response)

    def get_people(self, query=''):
        response = self.search(query=query)
        results = response['results']
        people = []
        if response['count'] > 0:
            for result in results:
                # dotmap allows us to access the items as names.name
                person = DotMap(result)
                people.append(person)
        return people

    def make_people(self, results):
        people = []
        for result in results:
            # dotmap allows us to access the items as names.name
            person = DotMap(result)
            people.append(person)
        return people


    def search(self, query='', paginate=False) -> dict:
        if self.apikey == None:
            raise Exception("Error: apikey required")
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.apikey
        }

        params = {
            "size": self.batch_size
        }
        if paginate:
            self.paginate = True
            params['paginate'] = True

        payload = query

        #calling PDS api            
        response = requests.post(self.pds_url, 
            headers = headers,
            params = params,
            data =  json.dumps(payload))

        # logger.info(json.loads(response.text))
        # logger.info(response.status_code)
        if(response.status_code != 200):
            raise Exception(f"Error: failure with response from PDS: {response.status_code}:{response.text}")
        
        if(response.json()['count'] < 1):
            logger.warn(f"WARNING: PDS returned no results for: {query}")

        if 'session_id' in response.json():
            self.session_id = response.json()['session_id']
        
        self.count = response.json()['count']
        self.total_count = response.json()['total_count']

        self.last_query = query
        self.response = response.json()
        return self.response

    def next(self) -> dict:
        if self.session_id is None:
            logger.warn(f"WARNING: trying to paginate with no session_id available.")
            return []

        if self.apikey == None:
            raise Exception("Error: apikey required")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.apikey
        }

        #calling PDS api            
        response = requests.post(self.pds_url + "/" + self.session_id, 
            headers = headers)

        # logger.info(json.loads(response.text))
        # logger.info(response.status_code)
        if(response.status_code != 200):
            raise Exception(f"Error: failure with response from PDS: {response.status_code}:{response.text}")
        

        if(response.json()['count'] < 1):
            # logger.warn(f"WARNING: PDS returned no results for: session_id: {self.session_id} with query: {self.last_query}")
            return {}

        if 'session_id' in response.json():
            self.session_id = response.json()['session_id']

        self.response = json.loads(response.text)
        self.count = response.json()['count']
        self.total_count = response.json()['total_count']
        return self.response
