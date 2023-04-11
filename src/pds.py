import requests
import os
import json
from common import logger
from dotmap import DotMap


# class Person(DotMap):


class People:
    def __init__(self, query, apikey):
        if apikey == None:
            raise Exception("Error: apikey required")
        if query == None:
            raise Exception("Error: query required")

        self.query = query
        self.apikey = apikey
        self.response = {}
        self.results = []
        self.count = 0
        self.total_count = 0
        try: 
            self.response = self.search(query=query, apikey=apikey)
            self.__setattr__('response', self.response)
            self.results = self.response['results']
            self.__setattr__('results', self.results)
            self.count = self.response['count']
            self.__setattr__('count', self.count)
            self.total_count = self.response['total_count']
            self.__setattr__('total_count', self.total_count)
        except Exception as e:
            logger.error(f"Error getting valid data from PDS: {e}")
            raise e

        self.people = self.getPeople()
        self.__setattr__('ppl', self.people)

    def __str__(self):
        return str(self.response)
    def __repr__(self):
        return str(self.response)

    def getPeople(self):
        people = []
        if self.count > 0:
            for result in self.results:
                # dotmap allows us to access the items as names.name
                person = DotMap(result)
                people.append(person)
        return people


    def search(self, query='', apikey=None):
        if self == None and apikey == None:
            raise Exception("Error: apikey required")

        pdsUrl = "https://go.dev.apis.huit.harvard.edu/ats/person/v3/search"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": apikey
        }

        payload = query

        #calling PDS api            
        response = requests.post(pdsUrl, 
            headers = headers,
            data =  json.dumps(payload))

        # logger.info(json.loads(response.text))
        # logger.info(response.status_code)
        if(response.status_code != 200):
            raise Exception("Error: failure with response from PDS")
        
        if(response.json()['count'] < 1):
            logger.warn(f"WARNING: PDS returned no results for: {query}")

        return json.loads(response.text)
            



# this is to get the value of a dotted element
def getValue(item):
    pieces = item.split(".")
    if len(pieces) < 1:
        return 
