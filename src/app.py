from common import isTaskRunning, logger, stack, AppConfig
import pds
from salesforce import HarvardSalesforce
from transformer import SalesforceTransformer
from departments import Departments

import os
import threading
import json
from datetime import datetime
if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 

#### DEV debugging section #########
from pprint import pformat

if stack == 'developer':
    f = open('../example_config.json')
    config = json.load(f)
    f.close()

    f = open('../example_pds_query.json')
    pds_query = json.load(f)
    f.close()
####################################


#### Collect action directive ######
action = os.getenv("action") or None
person_ids = os.getenv("person_ids") or []
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
            self.pds = pds.People(apikey=self.app_config.pds_apikey, batch_size=500)

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

    def process_people_batch(self, people: list=[]):

        self.transformer.hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getTargetConfig('Contact'), 
            source_data=people
        )

        data = {}
        # data = self.transformer.transform(source_data=people, target_object='Contact')
        data_gen = self.transformer.transform(source_data=people, target_object='Contact')
        for d in data_gen:
            # logger.info(d)
            for i, v in d.items():
                if i not in data:
                    data[i] = []
                data[i].append(v)


        time_now = datetime.now().strftime('%H:%M:%S')
        logger.info(f"**** Push Contact data to SF:  {time_now}")
        for object, object_data in data.items():
            logger.debug(f"object: {object}")
            logger.debug(pformat(object_data))

            self.hsf.pushBulk(object, object_data)

        self.transformer.hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getSourceConfig('pds'), 
            source_data=people
        )


        time_now = datetime.now().strftime('%H:%M:%S')
        logger.info(f"Starting the rest: {time_now}")

        data = {}

        # data = self.transformer.transform(source_data=people, target_object='Contact')
        data_gen = self.transformer.transform(source_data=people, source_name='pds', exclude_target_objects=['Contact'])
        for data_element in data_gen:
            # logger.info(pformat(data_element))
            data_elements = []
            if not isinstance(data_element, list):
                data_elements = [data_element]
            for d in data_elements:
                for i, v in d.items():
                    if i not in data:
                        data[i] = []
                    data[i].append(v)

        # threads = []
        # for target_object_name in self.app_config.config.keys():
        #     thread = threading.Thread(
        #         target=self.transformer.transform, 
        #         kwargs={"people": people, "source_name": 'pds', "target_object": target_object_name}
        #     )
        #     thread.start()
        #     threads.append(thread)
        # for thread in threads:
        #     thread.join()
        #     data.update(thread.return_value)

        


        threads = []
        time_now = datetime.now().strftime('%H:%M:%S')
        logger.info(f"**** Push Remaining People data to SF:  {time_now}")
        for object, object_data in data.items():
            logger.debug(f"object: {object}")
            logger.debug(pformat(object_data))

            # self.hsf.pushBulk(object, object_data)    
            thread = threading.Thread(target=self.hsf.pushBulk, args=(object, object_data))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()

        # NOTE: see notes on this function
        # hsf.setDeleteds(object='Contact', id_type='HUDA__hud_UNIV_ID__c', deleted_flag='lastName', ids=['31598567'])

    def update_single_person(self, huid: str):
        pds_query = self.app_config.pds_query
        if 'conditions' not in pds_query:
            pds_query['conditions'] = {}
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
        logger.info(f"Processing a full data load!")
        self.people_data_load(dry_run=dry_run)

        self.app_config.update_watermark("person")

    def people_data_load(self, dry_run=False, pds_query=None):
        start_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"Starting data load: {start_time}")

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

        count = 1
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"Starting batch {count}: {current_time}")

        if not dry_run:
            self.process_people_batch(people)
        logger.info(f"Finished batch {count}: {tally_count} of {total_count} at {current_time}")
        tally_count += current_count

        
        while(True):
            response = self.pds.next()
            count += 1
            if not response:
                break

            current_time = datetime.now().strftime('%H:%M:%S')
            logger.info(f"Starting batch {count}: {current_time}")

            results = response['results']
            people = self.pds.make_people(results)
            if not dry_run:
                self.process_people_batch(people)
            current_count = response['count']

            current_time = datetime.now().strftime('%H:%M:%S')
            logger.info(f"Finished batch {count}: {tally_count} of {total_count} at {current_time}")
            tally_count += current_count
        
        if tally_count != total_count:
            raise Exception(f"Error: PDS failed to retrieve all records")
        else:
            logger.info(f"successfully finished full data load in ")


sfpu = SalesforcePersonUpdates()

if action == 'single-person-update' and len(person_ids) > 0:
    sfpu.update_single_person(person_ids)
elif action == 'full-person-load':
    sfpu.full_people_data_load()
elif action == 'person-updates':
    sfpu.update_people_data_load()
elif action == 'full-department-load':
    sfpu.departments_data_load(type="full")
elif action == 'department-updates':
    sfpu.departments_data_load(type="update")
else: 
    logger.warn(f"Warning: app triggered without a valid action: {action}")

