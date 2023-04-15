import os
import json
from urllib.parse import urlencode
from datetime import datetime, date
from simple_salesforce import Salesforce 

from common import logger

class HarvardSalesforce:
    # initailize by connecting to salesforce
    def __init__(self, domain, username, password, consumer_key=None, consumer_secret=None, token=None):
        self.domain = domain
        self.username = username
        try: 
            logger.info(f"initializing to {self.domain} as {self.username}")
            if(token is not None):
                self.sf = Salesforce(
                    username=self.username,
                    password=password,
                    security_token=token,
                    domain=self.domain
                )
            elif(consumer_key is not None and consumer_secret is not None):
                self.sf = Salesforce(
                    username=self.username,
                    password=password,
                    consumer_key=consumer_key,
                    consumer_secret=consumer_secret,
                    domain=self.domain
                )
            else:
                raise Exception("well, that sucks, no valid credentials found")
        except Exception as e:
            logger.error(f"error connecting to salesforce: {e}")
            raise e
        

    # NOTE: this uses the Salesforce Bulk API
    # this API is generally async, but the way I'm using it (through simple-salesforce), it will wait (synchronously) for the job to finish 
    # this allows us to get the error logs without having to wait/check
    # that will probably be too slow to do fully sync
    # to make best use of this, we will need to async it with something like asyncio
    # NOTE: the Bulk API can take a max of 10000 records at a time
    # a single record will take anywhere from 2-50 seconds
    def pushBulk(self, object, data):
        logger.info(f"pushBulk to {object} with {data}")

        responses = self.sf.bulk.__getattr__(object).upsert(data, external_id_field='Id')
        logger.info(responses)
        for response in responses:
            if response['success'] != True:
                logger.error(f"Error in bulk data load: {response['errors']}")
                return False
        return True
    
    # this function will return a map of the contact ids to huid
    # NOTE: that there doesn't seem to be a good way to get multiple results without a soql query
    def getContactIds(self, id_type, ids):
        logger.info(f"getContactIds with the following huids: {ids}")
        ids_string = "'" + '\',\''.join(ids) + "'"
        sf_data = self.sf.query_all(f"SELECT Contact.id, {id_type} FROM Contact WHERE {id_type} IN({ids_string})")
        logger.info(f"got this data from salesforce: {sf_data}")
        return sf_data
    
    # NOTE: the integration user I'm using seems to only have GET/POST/HEAD permissions (on standard objects at least)
    #  update() requires PATCH and I don't know where that permission is in Salesforce yet, it would also need to be set by the admins, so maybe don't?
    # NOTE: this will set "all" deleted flags at once with the Bulk API
    def setDeleteds(self, object, id_type, deleted_flag, ids):
        data = []
        for id in ids:
            obj = {}
            obj[id_type] = id
            obj[deleted_flag] = True
            data.append(obj)

        responses = self.sf.bulk.__getattr__(object).upsert(data, external_id_field=id_type)
        logger.info(responses)

        for response in responses:
            if(response['success'] != True):
                logger.error(f"Error in setting deleted: {response['errors']}")
                return False

        # logger.info(f"id type: {id_type}")
        # result = self.sf.__getattr__(id_obj).update(f"{id_field}", {'flag_obj': 'Jegede2'})
        # logger.info(f"Updated deleted flag: {result}")
        return True

    # returns a mapping of the salesforce object field types
    # for example: { "Contact": { "Name": "string", "Email": "email", "Birthdate": "date" } }
    def getTypeMap(self, objects=[]):
        self.type_data = {}
        for object in objects:
            self.type_data[object] = {}
            description = self.sf.__getattr__(object).describe()
            for field in description.get('fields'):
                self.type_data[object][field['name']] = {}
                self.type_data[object][field['name']]['type'] = field['type'] 
                self.type_data[object][field['name']]['updateable'] = field['updateable']
                self.type_data[object][field['name']]['length'] = int(field['length'])

        return self.type_data
    
    # this will try to make sure the data going to the sf object is the right type
    def validate(self, object, field, value):
        if object not in self.type_data:
            logger.warn("Warning: no type data found, run getTypeMap() first for better performance")
            self.type_data([object])

        if field not in self.type_data[object]:
            raise Exception(f"Error: field ({field}) not found in type_data, please ensure this field is on that object")
        if 'type' not in self.type_data[object][field]:
            raise Exception(f"Error: field ({field}) does not have an associated `type`")
        if 'updateable' not in self.type_data[object][field]:
            raise Exception(f"Error: field ({field}) does not have an associated `updateable`")

        # if this is false, it means it's not a field we can update
        #   `Id` isn't something we can even try to edit
        if not self.type_data[object][field]['updateable'] and field != "Id":
            raise Exception(f"Error: field ({object}.{field}) is not editable")

        type = self.type_data[object][field]['type']
        if type in ["textarea", "string"]:
            length = self.type_data[object][field]['length']
            value = str(value)
            if value is None:
                return ""
            else:
                if len(value) > length:
                    value = value[:length]
                return str(value)
        if type in ["email"]:
            return str(value)
        if type in ["id"]:
            return value
        if type in ["date"]:
            # NOTE: Salesforce only liked dates from the year of our lord 1700-2400
            #       Salesforce also wants the date in an iso-8861 string
            #       It does not handle datetime as a date, so the 00:00:00 needs to be stripped off of datetimes
            value = value.split("T")[0].split(" ")[0]
            try:
                if value:
                    valid_date = datetime.strptime(value, '%Y-%m-%d').date()
                    if not (date(1700, 1, 1) <= valid_date <= date(2400, 1, 1)):
                        raise ValueError(f"Error: date out of range: {value}")
            except ValueError as e:
                raise Exception(f"Error: {e}")
            return value
        if type in ["datetime"]:
            try:
                if value:
                    valid_date = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S').date()
                    if not (date(1700, 1, 1) <= valid_date <= date(2400, 1, 1)):
                        raise ValueError(f"Error: date out of range: {value}")
            except ValueError as e:
                raise Exception(f"Error: {e}")
            return value
        if type in ["double"]:
            try: 
                return float(value)
            except ValueError as e:
                raise Exception(f"Error converting {object}.{field} ({value}) to double/float: {e}")
        else:
            raise Exception(f"Error: unhandled type: {type}")

    # format should look like { "OBJECT": { "id_name": "PDS ID NAME", "Ids": { "HARVARD ID": "SALESFORCE ID", ... } } }
    def getUniqueIds(self, config, people):
        self.unique_ids = {}
        for object in config.keys():
            ids = []
            self.unique_ids[object] = {}

            if 'Id' in config[object]:

                if 'salesforce' in config[object]['Id'] and 'pds' in config[object]['Id']:
                    # salesforce_id_name is the id name of the external id as it exists in salesforce
                    salesforce_id_name = config[object]['Id']['salesforce']
                    # person_id_name is the id name of the same id in pds
                    full_person_id_name = config[object]['Id']['pds']
                    person_branch = None
                    logger.info(f"full_person_id_name: {full_person_id_name}")

                    self.unique_ids[object]['id_name'] = full_person_id_name
                    if len(full_person_id_name.split(".")) > 1:
                        person_branch = full_person_id_name.split(".")[0]
                        person_id_name = full_person_id_name.split(".")[1]
                    else:
                        person_id_name = full_person_id_name

                    for person in people:
                        if person_branch is not None:
                            for b in person[person_branch]:
                                ids.append(str(b[person_id_name]))
                        else:
                            ids.append(str(person[person_id_name]))
    
                    ids_string = "'" + '\',\''.join(ids) + "'"
                    logger.debug(f"SELECT {object}.Id, {salesforce_id_name} FROM {object} WHERE {salesforce_id_name} IN({ids_string})")
                    sf_data = self.sf.query_all(f"SELECT {object}.Id, {salesforce_id_name} FROM {object} WHERE {salesforce_id_name} IN({ids_string})")
                    logger.debug(f"got this data from salesforce: {sf_data['records']}")
                    for record in sf_data['records']:
                        if 'Ids' not in self.unique_ids[object]:
                            self.unique_ids[object]['Ids'] = {}

                        self.unique_ids[object]['Ids'][record[salesforce_id_name]] = record['Id']

                else:
                    raise Exception(f"Error: match_to requires both 'salesforce' and 'pds' keys so we know which ids to match")

        logger.debug(f"unique_ids: {self.unique_ids}")
        return self.unique_ids
