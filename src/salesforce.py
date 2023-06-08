import json
import jsonschema
import logging
from datetime import datetime, date
from simple_salesforce import Salesforce, exceptions

from common import logger
logging.getLogger("simple_salesforce").setLevel(logging.WARNING)

class HarvardSalesforce:
    # initailize by connecting to salesforce
    def __init__(self, domain, username, password, consumer_key=None, consumer_secret=None, token=None):
        self.domain = domain
        self.username = username
        try: 
            logger.debug(f"Salesforce initializing to {self.domain} as {self.username}")
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
                raise Exception(f"Error: Salesforce connection requires a token or a consumer_key + consumer_secret combination")
        except Exception as e:
            logger.error(f"Error: Salesforce connection failed to {self.username}@{self.domain}: {e}")
            raise e

        # this should be set once we have a list of objects to query
        # through self.getTypeMap()
        self.type_data = {}      

    # NOTE: this uses the Salesforce Bulk API
    # this API is generally async, but the way I'm using it (through simple-salesforce), it will wait (synchronously) for the job to finish 
    # this allows us to get the error logs without having to wait/check
    # that will probably be too slow to do fully sync
    # to make best use of this, we will need to async it with something like asyncio
    # NOTE: the Bulk API can take a max of 10000 records at a time
    # a single record will take anywhere from 2-50 seconds
    # dupe: this makes sure we don't keep retrying a dupe check
    def pushBulk(self, object, data, dupe=False):
        logger.debug(f"pushBulk to {object} with {data}")

        responses = self.sf.bulk.__getattr__(object).upsert(data, external_id_field='Id')
        created_count = 0
        updated_count = 0
        error_count = 0
        for index, response in enumerate(responses):
            if response['success'] != True: 
                
                errored_data = data[index]
                logger.error(f"Error in bulk data load: {response['errors']} ({errored_data})")

                if response['errors'][0]['statusCode'] == 'DUPLICATES_DETECTED':

                    if dupe:
                        logger.error(f"Error: DUPLICATE DETECTED (unresoved): {errored_data}")
                    else:
                        logger.error(f"Error: DUPLICATE DETECTED -- Errored Data: {errored_data}")
                        if self.check_duplicate(object, errored_data):
                            error_count -= 1
                error_count += 1
            else:
                if response['created']:
                    created_count += 1
                else:
                    updated_count += 1
                logger.debug(response)
        if updated_count > 0:
            logger.info(f"Updated {object} Records: {updated_count}")
        if created_count > 0:
            logger.info(f"Created {object} Records: {created_count}")
        if error_count > 0:
            logger.info(f"Errored {object} Records: {error_count}")
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
    
    # check the validity of the config
    # this does a basic json check
    # then a more extensive jsonschema check
    # then it makes calls to salesforce to get the models and fields referenced in the config
    #   so we can know if all the data structures exist
    def validateConfig(self, config, dry_run=False):
        try: 

            # first check to see if the config is valid as json
            try: 
                json.dumps(config)
            except ValueError:
                raise ValueError(f"Config is not valid as JSON")
            
            # now use the jsonschema definition to validate the format
            try:
                f = open('config.schema.json')
            except: 
                try: 
                    f = open('../config.schema.json')
                except Exception as e:
                    logger.error(f"Error: unable to find schema")
                    raise e
            schema = json.load(f)
            f.close()

            try: 
                jsonschema.validate(instance=config, schema=schema)
            except Exception as e: 
                logger.error(f"Error: validation of config against schema failed")
                raise e
            
            # now we make sure the objects exist in salesforce
            if not dry_run:
                try:
                    config_field = None
                    for object in config:

                        description = self.sf.__getattr__(object).describe()
                        
                        # in here we check that all fields we're trying to push to exist in the target salesforce
                        for config_field in config[object]['fields'].keys():
                            if config_field not in [f['name'] for f in description.get('fields')]:
                                raise Exception(f"Error: {config_field} not found in {object}")


                except Exception as e:
                    logger.error(f"Error: Salesforce Object {object} or field {config_field} not found in target Salesforce")
                    raise e


            return True
        except Exception as e: 
            logger.error(f"Error: validation exception: {e}")
            # raise e
            return False


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
                self.type_data[object][field['name']]['externalId'] = field['externalId']
                self.type_data[object][field['name']]['unique'] = field['externalId']

        return self.type_data
    
    # this will try to make sure the data going to the sf object is the right type
    def validate(self, object, field, value, identifier):
        logger.debug(f"validating the value ({value}) for the field: {object}.{field} from {identifier}")
        if object not in self.type_data:
            logger.warn("Warning: no type data found, run getTypeMap() first for better performance")
            self.type_data([object])

        if field not in self.type_data[object]:
            raise Exception(f"Error: field ({field}) not found in type_data, please ensure this field is on that object")
        if 'type' not in self.type_data[object][field]:
            raise Exception(f"Error: field ({field}) does not have an associated `type`")
        if 'updateable' not in self.type_data[object][field]:
            raise Exception(f"Error: field ({field}) does not have an associated `updateable`")

        # NOTE: Salesforce cannot take a null value directly, it needs to take the value: '#N/A'?
        if not value:
            return None

        if not isinstance(value, (str, bool, int)):
            value_type = type(value)
            logger.error(f"Error: value ({value}) for {object}.{field} is not a valid type ({value_type}). Identifier: {identifier}")
            return None

        # if this is false, it means it's not a field we can update
        #   `Id` isn't something we can even try to edit
        if not self.type_data[object][field]['updateable'] and field != "Id":
            raise Exception(f"Error: field ({object}.{field}) is not editable")

        field_type = self.type_data[object][field]['type']
        if field_type in ["textarea", "string"]:
            length = self.type_data[object][field]['length']
            if isinstance(value, bool):
                if value:
                    return 1
                else:
                    return 0

            value = str(value)
            if value is None:
                return None
            else:
                if len(value) > length:
                    value = value[:length]
                return str(value)
        elif field_type in ["email"]:
            return str(value)
        elif field_type in ["id", "reference"]:
            return value
        elif field_type in ["date"]:
            # NOTE: Salesforce only liked dates from the year of our lord 1700-2400
            #       Salesforce also wants the date in an iso-8861 string
            #       It does not handle datetime as a date, so the 00:00:00 needs to be stripped off of datetimes
            value = value.split("T")[0].split(" ")[0]
            try:
                if value:
                    valid_date = datetime.strptime(value, '%Y-%m-%d').date()
                    if not (date(1700, 1, 1) <= valid_date <= date(2400, 1, 1)):
                        # raise ValueError(f"Error: date out of range: {value}")
                        logger.error(f"Error: date out of range: {value}. Indentifier: {identifier}")
                        return None
            except ValueError as e:
                logger.error(f"Error: {e}. Indentifier: {identifier}")
                return None
            return value
        elif field_type in ["datetime"]:
            try:
                if value:
                    # we want to try both formats for datetime
                    try:
                        valid_date = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S').date()
                    except:
                        value = value.replace(" ", "T")
                        valid_date = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S').date()
                    if not (date(1700, 1, 1) <= valid_date <= date(2400, 1, 1)):
                        logger.error(f"Error: date out of range: {value}. Indentifier: {identifier}")
                        return None
            except ValueError as e:
                logger.error(f"Error: {e}. Indentifier: {identifier}")
                return None
            return value
        elif field_type in ["double"]:
            try: 
                return float(value)
            except ValueError as e:
                logger.error(f"Error converting {object}.{field} ({value}) to double/float: {e}. Identifier: {identifier}")
                return None
        else:
            logger.error(f"Error: unhandled field_type: {field_type}. Please check config and target Salesforce instance")
            return None

    # getUniqueIds 
    # output format should look like:
    #   { "SF OBJECT NAME": { "id_name": "PDS ID NAME", "Ids": { "HARVARD ID": "SALESFORCE ID", ... } } }
    def getUniqueIds(self, config, source_data, target_object=None):
        
        if target_object is None or not self.unique_ids:
            self.unique_ids = {}
        for object in config.keys():
            if target_object is not None and target_object != object:
                continue

            # unique_object_fields = [i for i, obj in self.type_data[object].items() if obj['unique'] or obj['externalId']]
            # unique_object_fields.append('Email')
            # unique_object_fields.append('FirstName')
            # unique_object_fields.append('LastName')

            self.unique_ids[object] = {}

            if 'Id' in config[object]:

                # salesforce_id_name is the id name of the external id as it exists in salesforce
                salesforce_id_name = config[object]['Id']['salesforce']
                source_name = config[object]['source']

                # if salesforce_id_name not in unique_object_fields:
                #     unique_object_fields.append(salesforce_id_name)

                # full_source_id_value is the id name of the SAME external id as it exists in the source data (e.g. pds or departments)
                if source_name in config[object]['Id']:
                    full_source_id_value = config[object]['Id'][source_name]
                else:
                    raise Exception(f"Error: source {source_name} not found in config. (Did you remember to slice the config?)")

                # if it's a list, we need to do all of them
                if isinstance(full_source_id_value, list):
                    id_names = full_source_id_value
                else:
                    id_names = [full_source_id_value]

                self.unique_ids[object]['id_name'] = full_source_id_value
                self.unique_ids[object]['Ids'] = {}
                
                for full_source_data_id_name in id_names:

                    source_data_object_branch = None
                    logger.debug(f"full_source_data_id_name: {full_source_data_id_name}")


                    if len(full_source_data_id_name.split(".")) > 1:
                        source_data_object_branch = full_source_data_id_name.split(".")[0]
                        source_data_id_name = full_source_data_id_name.split(".")[1]
                    else:
                        source_data_id_name = full_source_data_id_name

                    ids = []

                    # example: person in people
                    for source_data_object in source_data:
                        # if it's a branch
                        if source_data_object_branch is not None:
                            for b in source_data_object[source_data_object_branch]:
                                ids.append(str(b[source_data_id_name]))
                        # if it's not a branch
                        else:
                            ids.append(str(source_data_object[source_data_id_name]))
    
                    batch_size = 500
                    for i in range(0, len(ids), batch_size):
                        try:
                            batch = ids[i:i + batch_size]

                            # fields_string = ','.join(unique_object_fields)
                            ids_string = "'" + '\',\''.join(batch) + "'"
                            # select_string = f"SELECT {object}.Id, {fields_string} FROM {object} WHERE {salesforce_id_name} IN({ids_string})"
                            select_string = f"SELECT {object}.Id, {salesforce_id_name} FROM {object} WHERE {salesforce_id_name} IN({ids_string})"
                            logger.debug(select_string)
                            sf_data = self.sf.query_all(select_string)
                            logger.debug(f"got this data from salesforce: {sf_data['records']}")

                            # go through each record?
                            for record in sf_data['records']:
                                
                                if 'Ids' not in self.unique_ids[object]:
                                    self.unique_ids[object]['Ids'] = {}
                                self.unique_ids[object]['Ids'][str(record[salesforce_id_name])] = record['Id']



                        except exceptions.SalesforceGeneralError as e:
                            logger.error(f"Error: {e} with {select_string}")
                            raise e             
                        except Exception as e:
                            raise Exception(f"Error: {e} with {select_string}")                     

        logger.debug(f"unique_ids: {self.unique_ids}")
        return self.unique_ids

    # TODO: this
    # verify_logging_object
    # makes sure the logging object exists on the target instance
    def verify_logging_object(self):

        # check if MyObject exists
        object_name = 'HUD__Logging__c'
        object_description = self.sf.describe()

        if object_name in [obj['name'] for obj in object_description['sobjects']]:
            logger.debug(f"{object_name} exists")
            object_fields = self.sf.MyObject__c.describe()['fields']
            # check if myField exists and is of type string
            for field_name in ['error__c', 'warning__c', 'info__c']:
                field_exists = False
                for field in object_fields:
                    if field['name'] == field_name:
                        field_exists = True
                        if field['type'] == 'string':
                            logger.info(f"{field_name} exists and is of type string")
                        else:
                            logger.info(f"{field_name} exists but is not of type string")
                        break
            if not field_exists:
                logger.info(f"{field_name} does not exist")
                return False
            return True
        else:
            logger.info(f"{object_name} does not exist")
            return False


    # create_logging_object
    # NOTE: this won't work for namespaced objects (objects that start with: "SOMETHING__")
    #   so it's probably not going to work for us
    #   Leaving this method in though to remind me of this limitation
    def create_logging_object(self):
        mdapi = self.sf.mdapi
        if not self.verify_logging_object():

            # Create the custom object
            custom_object = mdapi.CustomObject(
                fullName="HUD__Logging__c",
                label="HUD Log",
                pluralLabel="HUD Logs",
                nameField=mdapi.CustomField(
                    label="LogName",
                    type=mdapi.FieldType("Text")
                ),
                fields=[
                    {
                        'fullName': 'timestamp__c',
                        'label': 'Timestamp',
                        'type': 'DateTime'
                    },
                    {
                        'fullName': 'log__c',
                        'label': 'Log',
                        'type': 'TextArea'
                    },
                    {
                        'fullName': 'log_type__c',
                        'label': 'Log Type',
                        'type': 'Text',
                        'length': 20
                    }
                ],
                deploymentStatus=mdapi.DeploymentStatus("Deployed"),
                sharingModel=mdapi.SharingModel("ReadWrite")
            )

            mdapi.CustomObject.create(custom_object)



        return self.verify_logging_object()
    

    # this method is trying to find an Id for a record that failed as a dupe
    # the `errored_data_object` should be of the same record that triggered the error
    def check_duplicate(self, object_name, errored_data_object, dry_run=False):

        # first we get all of the externalids/uniques for the object that we collected in type data
        unique_object_fields = [i for i, obj in self.type_data[object_name].items() if obj['unique'] or obj['externalId']]

        # build the where clause
        whereses = []
        where_clause = ""
        for field in unique_object_fields:
            if field in errored_data_object:
                field_value = errored_data_object[field]
                whereses.append(f"{field} = '{field_value}'")

        # this is to handle the standard contact duplicate matching rule, or at least the most common breaking of it
        # see: https://help.salesforce.com/s/articleView?language=en_US&id=sf.matching_rules_standard_contact_rule.htm&type=5
        if object_name == 'Contact':
            standard_contact_rule_string = ''
            email = None
            first_name = None
            last_name = None
            if 'Email' in errored_data_object and 'FirstName' in errored_data_object and 'LastName' in errored_data_object:
                email = errored_data_object['Email']
                first_name = errored_data_object['FirstName']
                last_name = errored_data_object['LastName']
                standard_contact_rule_string = f"(Email = '{email}' and LastName = '{last_name}' and FirstName = '{first_name}')"
                
                whereses.append(f"{standard_contact_rule_string}")
        
        where_clause = " or ".join(whereses)

        select_string = f"SELECT {object_name}.Id FROM {object_name} WHERE {where_clause}"
        logger.debug(select_string)
        sf_data = self.sf.query_all(select_string)
        logger.debug(f"got this data from salesforce: {sf_data['records']}")

        # go through each record 
        if len(sf_data['records']) > 1:
            logger.error(f"Error: too many records found on object {object_name} with this data: {errored_data_object} -- Ids: {sf_data}")
        elif len(sf_data['records']) < 1:
            logger.error(f"Error: no records found on object {object_name} with this data: {errored_data_object}")
        else:
            found_id = sf_data['records'][0]['Id']
            logger.debug(f"Success resolving duplicate! id: {found_id} trying to re-push record")
            errored_data_object['Id'] = found_id
            if not dry_run:
                self.pushBulk(object_name, [errored_data_object], dupe=True)
            return True





        # then we use those ids to see if there's an Id for the record we're looking for
        # we can do that in a single soql call
        #   select Id from object_name where externalid1 = X || externalid2 = Y || email = Z and firstname and lastname ....
        

