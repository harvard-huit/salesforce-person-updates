from common import isTaskRunning, logger, stack, AppConfig
import pds
from salesforce import HarvardSalesforce
from transformer import SalesforceTransformer
from departments import Departments

import os
import json
from datetime import datetime
if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 


#### DEV debugging section #########
from pprint import pprint, pp, pformat

f = open('../example_config.json')
config = json.load(f)
f.close()

f = open('../example_pds_query.json')
pds_query = json.load(f)
f.close()
####################################

class SalesforcePersonUpdates:
    def __init__(self):
        try:
            if(stack != "developer"):
                logger.info("Checking if task is already running")
                if isTaskRunning() and stack != 'developer':
                    logger.warning("WARNING: application already running")
                    exit()

            # TODO: GET data/watermark from dynamodb based on client
            self.app_config = AppConfig("huit-full-sandbox", "aais-services-salesforce-person-updates-dev")

            # initializing a salesforce instance
            # hsf = HarvardSalesforce(
            #     domain = 'test',
            #     username = os.getenv('SF_USERNAME'),
            #     password = os.getenv('SF_PASSWORD'),
            #     consumer_key = os.getenv('SF_CLIENT_KEY'),
            #     consumer_secret = os.getenv('SF_CLIENT_SECRET')
            # )
            # self.hsf = HarvardSalesforce(
            #     domain = os.getenv('SF_DOMAIN'),
            #     username = os.getenv('SF_USERNAME'),
            #     password = os.getenv('SF_PASSWORD'),
            #     token = os.getenv('SF_SECURITY_TOKEN'),
            # )
            self.hsf = HarvardSalesforce(
                domain = self.app_config.salesforce_domain,
                username = self.app_config.salesforce_username,
                password = self.app_config.salesforce_password,
                token = self.app_config.salesforce_token,
                consumer_key = self.app_config.salesforce_token,
                consumer_secret = self.app_config.salesforce_token
            )            

            # check salesforce for required objects for push and get a map of the types
            self.hsf.getTypeMap(self.app_config.config.keys())

            # validate the config
            self.hsf.validateConfig(self.app_config.config)

            # TODO: implement updates_only
            self.updates_only = os.getenv('UPDATES_ONLY') or False

            # self.pds_apikey = os.getenv("PDS_APIKEY")
            # initialize pds
            self.pds = pds.People(apikey=self.app_config.pds_apikey)

            # TODO: GET list of updated people since watermark 



            self.transformer = SalesforceTransformer(config=self.app_config.config, hsf=self.hsf)

            # self.process_people_batch(people)



        except Exception as e:
            logger.error(f"Run failed with error: {e}")
            raise e


    # valid types are "full" and "update"
    def departments_data_load(self, type="full"):
        logger.info(f"Starting a department {type} load")
        self.departments = Departments(apikey=os.getenv("DEPT_APIKEY"))

        hashed_departments = self.departments.departments
        logger.debug(f"Successfully got {len(self.departments.results)} departments")

        watermark = self.app_config.watermarks["department"]

        # the api does not have a "get updates" endpoint, so we need to filter here
        results = self.departments.results
        updated_results = []
        if type=="update":
            for index, department in hashed_departments.items():
                department_datetime = datetime.strptime(department['updateDate'], '%Y-%m-%d %H:%M:%S').date()
                if department_datetime > watermark:
                    updated_results.append(department)
            results = updated_results        

        # data will have the structure of { "OBJECT": [{"FIELD": "VALUE"}, ...]}
        data = {}
        data = self.transformer.transform(source_data=results, source_name='departments')

        logger.info(f"**** Push Departments to SF  ****")
        for object, object_data in data.items():
            logger.debug(f"object: {object}")
            logger.debug(pformat(object_data))

            self.hsf.pushBulk(object, object_data)    

        self.app_config.update_watermark("department")


    def process_people_batch(self, people=[]):

        data = {}
        data = self.transformer.transform(source_data=people, target_object='Contact')

        logger.info(f"**** Push Contact data to SF  ****")
        for object, object_data in data.items():
            logger.info(f"object: {object}")
            logger.info(pformat(object_data))

            self.hsf.pushBulk(object, object_data)

        data = {}
        data = self.transformer.transform(source_data=people, source_name='pds', exclude_target_objects=['Contact'])

        logger.info(f"**** Push Remaining People data to SF  ****")
        for object, object_data in data.items():
            logger.info(f"object: {object}")
            logger.info(pformat(object_data))

            self.hsf.pushBulk(object, object_data)    

        # NOTE: see notes on this function
        # hsf.setDeleteds(object='Contact', id_type='HUDA__hud_UNIV_ID__c', deleted_flag='lastName', ids=['31598567'])

    def update_single_person(self, huid):
        pds_query = self.app_config.pds_query
        pds_query['conditions']['univid'] = huid
        people = self.pds.get_people(pds_query)
        self.process_people_batch(people=people)

    def update_people_data_load(self, watermark: datetime=None):
        if not watermark:
            watermark = self.app_config.watermarks['person']

        pds_query = self.app_config.pds_query
        pds_query['conditions']['updateDate'] = ">" + watermark.strftime('%Y-%m-%d %H:%M:%S')
        self.people_data_load(pds_query=pds_query)

        self.app_config.update_watermark("person")

    def full_people_data_load(self, dry_run=False):
        self.people_data_load(dry_run=dry_run)

        self.app_config.update_watermark("person")

    def people_data_load(self, dry_run=False, pds_query=None):
        # without the pds_query, it uses the "full" configured query
        if pds_query is None:
            pds_query = self.app_config.pds_query
        response = self.pds.search(pds_query, paginate=True)
        current_count = response['count']
        size = self.pds.batch_size
        total_count = response['total_count']
        tally_count = current_count
        results = response['results']
        people = self.pds.make_people(results)
        logger.info(current_count)

        if not dry_run:
            self.process_people_batch(people)
        
        while(True):
            response = self.pds.next()
            if not response:
                break
            results = response['results']
            people = self.pds.make_people(results)
            if not dry_run:
                self.process_people_batch(people)
            current_count = response['count']
            tally_count += current_count

            logger.info(current_count)
        
        if current_count != total_count:
            raise Exception(f"Error: PDS failed to retrieve all records")
        else:
            logger.info(f"successfully finished full data load in {duration}")


sfpu = SalesforcePersonUpdates()
# sfpu.update_single_person("80719647")
# sfpu.full_people_data_load()
# sfpu.update_people_data_load()
# sfpu.departments_data_load(type="full")
sfpu.departments_data_load(type="update")

