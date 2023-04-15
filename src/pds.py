import requests
import os
import json
from common import logger
from dotmap import DotMap


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
# (purposely not in the class)
def getValue(field, person, condition={}):


    if field in person:
        return person[field]
    else:
        if "." in field:
            branch_name = field.split(".")[0]
            field_name = field.split(".")[1]

            condition_index = None
            condition_value = None
            if condition:
                condition_index = condition.keys()[0]
                condition_value = condition[condition_index]

            if branch_name not in person:
                raise Exception(f"Error: {branch_name} not found in person {person}")
            
            condition_branch = None
            if "." in condition_index:
                pieces = condition_index.split(".")
                condition_branch = pieces[0]
                if condition_branch not in person:
                    raise Exception(f"Error: condition source ({condition_index}) not found in person ({person})")
                # split off the branch value
                condition_index = pieces[1:]
                if "." in condition:
                    # TODO: finish this
                    pass                    


            data = []
            for branch in person[branch_name]:
                if field_name in branch:
                    if condition:
                        data.append(branch[field_name])
                else:
                    if "." in field_name:
                        pieces = field_name.split(".")
                        if pieces[0] in branch:
                            if pieces[1] in branch[0]:
                                data.append(branch[pieces[0]][pieces[1]])
                    else:
                        raise Exception(f"Error: {field_name} not found in branch {branch}")
            if len(data) == 1:
                return data[0]
            else:
                return data