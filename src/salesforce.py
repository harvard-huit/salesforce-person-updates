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
        # list of job references
        self.jobs = []
        self.unique_ids = {}
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
    # this API is generally async, but the way I'm using it, it will wait (synchronously) for the job to finish 
    # this allows us to get the error logs without having to wait/check
    # that will probably be too slow to do fully sync
    # to make best use of this, we will need to async it with something like asyncio/threading
    # NOTE: the Bulk API can take a max of 10000 records at a time
    # a single record will take anywhere from 2-50 seconds
    # dupe: this makes sure we don't keep retrying a dupe check
    def pushBulk(self, object, data, dupe=False, id_name='Id'):
        if data is None or len(data) == 0:
            logger.warn(f"No data to push to {object}")
            return True
        logger.debug(f"upsert to {object} with {len(data)} records")

        # This will send the upsert as async, the results will just be a jobId that you can query for results later (in theory)
        # responses = self.sf.bulk.__getattr__(object).upsert(data, external_id_field=id_name, batch_size=5000, use_serial=True, bypass_results=True)

        # This is the sync/blocking version of the upsert, it will return with the results of each record
        responses = self.sf.bulk.__getattr__(object).upsert(data, external_id_field=id_name)
        
        
        # Keeping this in here as a way to work with async pushes in the future
        # logger.info(f"{responses}")
        # for response in responses:
        #     if 'job_id' in response:
        #         self.jobs.append(response['job_id'])
        #     elif 'bypass_results' not in response:
        #         logger.warning(f"Bulk response with no job id: {response}")
        # self.log_jobs()


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
    
    # this will check for outstanding jobs and log them if they're done
    # this does NOT work to get results
    # a call to /jobs/ingest/JOBID will return as it should, in json, but will only have 
    #   - number of processed records 
    #   - number of failed records
    # That leaves us with no way to determine what actually went wrong
    # /jobs/ingest/JOBID/successfulResults is supposed to return a CSV of the actual results of each record
    #   However, it does not return anything. (same with /jobs/ingest/JOBID/failedResults)
    def log_jobs(self):


        # NOTE: this query can get the status, but not results (i.e. if the job is finished)
        # job_id_string = [job['job_id'] for job in self.jobs]
        # sf_data = self.sf.query_all(f"SELECT Id, Status, JobType, CreatedBy.Name, CreatedDate, CompletedDate, NumberOfErrors FROM AsyncApexJob WHERE Id IN({job_id_string})")
        

        for job in self.jobs:
            endpoint = "jobs/ingest/" + job['job_id']
            response = self.sf.restful(endpoint)
            logger.info("******************************")
            logger.info(f"object: {response['object']}")
            logger.info(f"state: {response['state']}")
            logger.info(f"numberRecordsProcessed: {response['numberRecordsProcessed']}")
            if int(response['numberRecordsProcessed']) > 0:
                success_endpoint = f"{endpoint}/successfulResults/"
                # NOTE: sf.restful() will not work on this endpoint
                #       sf.restful() is not documented well (at all??)
                #       but through trial/error, it's apparent it tries to do a json.dumps() and will fail on a payload that isn't json
                #       you need to use requests and add the session_id from the sf object to the Auth bearer token
                response = self.sf.restful(success_endpoint)
            logger.info(f"numberRecordsFailed: {response['numberRecordsFailed']}")
            if response['numberRecordsFailed'] > 0:
                success_endpoint = f"{endpoint}/failedResults/"
                response = self.sf.restful(success_endpoint)


    # this function will return a map of the contact ids to huid
    # NOTE: that there doesn't seem to be a good way to get multiple results without a soql query
    def getContactIds(self, id_type, ids):
        logger.debug(f"getContactIds with the following huids: {ids}")
        ids_string = "'" + '\',\''.join(ids) + "'"
        sf_data = self.sf.query_all(f"SELECT Contact.id, {id_type} FROM Contact WHERE {id_type} IN({ids_string})")
        logger.debug(f"got this data from salesforce: {sf_data}")
        return sf_data
    
    # this will return a list of all of the values found on the object
    def get_all_external_ids(self, object_name, external_id):
        logger.debug(f"get_all_external_ids getting all {external_id} from {object_name}")
        

        sf_data = self.sf.query_all(f"SELECT {external_id} FROM {object_name}")
        logger.debug(f"got this data from salesforce: {sf_data}")
        all_ids = []
        for record in sf_data['records']:
            if record[external_id] is not None:
                all_ids.append(record[external_id])

        logger.debug(all_ids)
        return all_ids
    
    def flag_field(self, object_name: str, external_id: str, flag_name: str, value: any, ids: list):
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            try:
                batch = ids[i:i + batch_size]
                data = []
                for id in batch:
                    data_object = {}
                    data_object[external_id] = id
                    data_object[flag_name] = value
                    data.append(data_object)
                self.pushBulk(object=object_name, data=data, id_name=external_id)

            except Exception as e:
                logger.error("Failure to flag fields")
                raise



    # get all data from an object given the reference and ids
    def get_object_data(self, object_name, contact_ref, contact_ids):
        logger.debug(f"get_all_data with the following ids: {contact_ids}")
        ids_string = "'" + '\',\''.join(contact_ids) + "'"
        sf_data = self.sf.query_all(f"SELECT Fields(ALL) FROM {object_name} WHERE {contact_ref} IN({ids_string}) LIMIT 100")
        logger.debug(f"got this data from salesforce: {sf_data}")
        return sf_data
    
    # this is meant to take the output from compare_records and push it to a tsv file
    # with no output_file, it will just return the data as a string
    def compare_to_tsv(self, data, output_file:str=None):
        tsv_data = f"Id\tField\tSand Value\tProd Value\tMatch\n"
        id_string = None
        if 'ids' in data:
            id_string = f"Mismatched ids\t\t{data['ids']['sand']}\t{data['ids']['prod']}\n"
            del data['ids']
        for id_value, id_data in data.items():
            tsv_data += "\n" + "\n".join([f"{id_value}\t{index}\t{res['sand']}\t{res['prod']}\t{res.get('match', None)}" for index, res in id_data.items()]) + "\n"
            if output_file:
                with open(output_file, 'w') as file:
                    file.write(tsv_data)
                        
        if id_string:
            tsv_data += "\n" + id_string

        return tsv_data
    

    # this is intended to compare record sets (coming from a get_data_object or other soql result set)
    def compare_records(self, object_name, ref_field, dataset1, dataset2, all=True):
        logger.debug(f"Comparing {object_name} Records:")

        # we want to skip these fields, they'll always be different
        ignore_fields = ['Id', 'attributes', 'OwnerId', 'Name', 'CreatedDate', 'CreatedById', 'LastModifiedDate', 
                         'LastModifiedById', 'SystemModstamp', 'AccountId', 'LastActivityDate', 'LastViewedDate', 
                         'LastReferenceDated', 'IAM_Grouper_WS_Customers__c', 'IAM_Grouper_App_Customers__c', 
                         'PAM__Partner_Server_URL_80__c', 'IAM_Harvard_Key_Auth_CAS_Owners__c', 'IAM_Midas_Customers__c',
                         'CloudAware_Application__c', 'PAM__Contact_Score_Rating__c', 'PAM__Contact_Score__c',
                         'IAM_IDP_Customers__c', 'IAM_IIQ_Customers__c'
                         ]

        result = {}

        if len(dataset1['records']) != len(dataset2['records']):
            logger.error(f"Error: not correct number of records")
            logger.error(f"Sand has:")
            for record in dataset1['records']:
                logger.error(f"{record[ref_field]}")
            logger.error(f"Prod has:")
            for record in dataset2['records']:
                logger.error(f"{record[ref_field]}")
            result['ids'] = {
                "sand": [record[ref_field] for record in dataset1['records']],
                "prod": [record[ref_field] for record in dataset2['records']]
            }

        for contact2 in dataset2['records']:
            for contact1 in dataset1['records']:
                found_record = False
                if contact1[ref_field] == contact2[ref_field]:
                    id_value = contact1[ref_field]
                    logger.debug(f"Record {ref_field}: {id_value}")
                    found_record = True
                    for field, value in contact2.items():
                        this_result = {}
                        if field not in contact1:
                            logger.error(f"{field} not found in test instance")
                            continue
                        if field in ignore_fields:
                            continue

                        if contact1[field] == contact2[field]:
                            if all:
                                logger.debug(f"{field}, {contact1[field]}, {contact2[field]}, MATCH")
                                this_result = {
                                    "sand": contact1[field],
                                    "prod": contact2[field],
                                    "match": True
                                }
                                if id_value not in result:
                                    result[id_value] = {}
                                result[id_value][field] = this_result
                        else:
                            logger.debug(f"{field}, {contact1[field]}, {contact2[field]}, ERROR")
                            this_result = {
                                "sand": contact1[field],
                                "prod": contact2[field],
                                "match": False
                            }
                            if id_value not in result:
                                result[id_value] = {}
                            result[id_value][field] = this_result

        return result


    # this function soft-deletes the records included in the list argument
    # WARNING: this currently has no real world use, it's just being used for debugging purposes
    def delete_records(self, object_name: dict, ids: list):
        logger.warn(f"WARNING: bulk soft DELETE to {object} with {ids}")
        logger.warn(f"WARNING: this operation has no real world use and should only be used for debugging purposes in test orgs")

        data = []
        for id in ids:
            data.append({
                'Id': id
            })
        responses = self.sf.bulk.__getattr__(object_name).delete(data,batch_size=10000,use_serial=True)
        logger.warn(f"WARNING: DELETED ids from {object_name} with response: {responses}")
        return True

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
        logger.warn(responses)

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
        elif field_type in ["boolean"]:
            try:
                return value in [True, False]
            except ValueError as e:
                logger.error(f"Error: field {field} is a boolean, must be True or False. Tried value: {value}")
        else:
            logger.error(f"Error: unhandled field_type: {field_type}. Please check config and target Salesforce instance")
            return None

    # getUniqueIds 
    # output format should look like:
    #   { "SF OBJECT NAME": { "id_name": "PDS ID NAME", "Ids": { "HARVARD ID": "SALESFORCE ID", ... } } }
    def getUniqueIds(self, config, source_data, target_object=None):
                    
        for object in config.keys():
            if target_object is not None and target_object != object:
                continue

            # unique_object_fields = [i for i, obj in self.type_data[object].items() if obj['unique'] or obj['externalId']]
            # unique_object_fields.append('Email')
            # unique_object_fields.append('FirstName')
            # unique_object_fields.append('LastName')

            if object not in self.unique_ids:
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
                            if source_data_object_branch in source_data_object:
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
                        if field['level'] == 'string':
                            logger.debug(f"{field_name} exists and is of type string")
                        else:
                            logger.debug(f"{field_name} exists but is not of type string")
                        break
            if not field_exists:
                logger.warn(f"{field_name} does not exist")
                return False
            return True
        else:
            logger.warn(f"{object_name} does not exist")
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
        

