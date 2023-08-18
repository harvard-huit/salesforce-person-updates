from logging import LogRecord
from common import isTaskRunning, logger, stack, AppConfig
import pds
from salesforce import HarvardSalesforce
from transformer import SalesforceTransformer
from departments import Departments

import os
import threading
import json
import logging
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
if os.getenv("person_ids"):
    person_ids = json.loads(os.getenv("person_ids"))
else:
    person_ids = []
####################################

class SalesforcePersonUpdates:
    def __init__(self):
        try:
            if(stack != "developer" and False):
                # NOTE: this doesn't work / make sense as is
                #       this also needs to check if it's running on a particular SF instance
                logger.info("Checking if task is already running")
                if isTaskRunning() and stack != 'developer':
                    logger.warning("WARNING: application already running")
                    exit()

            self.salesforce_instance_id = os.getenv("SALESFORCE_INSTANCE_ID", None)
            self.table_name = os.getenv("TABLE_NAME", None)

            current_time_mash = datetime.now().strftime('%Y%m%d%H%M')
            self.run_id = f"{self.salesforce_instance_id}_{current_time_mash}"


            if os.getenv("LOCAL") == "True":
                self.app_config = AppConfig(id=None, table_name=None, local=True)
            else:
                if self.salesforce_instance_id is None or self.table_name is None:
                    raise Exception("ERROR: SALESFORCE_INSTANCE_ID and TABLE_NAME are required env vars, these tell us where to get the configuration.")

                self.app_config = AppConfig(id=self.salesforce_instance_id, table_name=self.table_name)

            self.hsf = HarvardSalesforce(
                domain = self.app_config.salesforce_domain,
                username = self.app_config.salesforce_username,
                password = self.app_config.salesforce_password,
                token = self.app_config.salesforce_token,
                consumer_key = self.app_config.salesforce_client_key,
                consumer_secret = self.app_config.salesforce_client_secret
            )

            second_salesforce_username = os.getenv('SF_USERNAME2', None)
            if second_salesforce_username:
                second_salesforce_password = os.getenv('SF_PASSWORD2', None)
                second_salesforce_token = os.getenv('SF_SECURITY_TOKEN2', None)
                second_salesforce_domain = os.getenv('SF_DOMAIN2', None)

                self.hsf2 = HarvardSalesforce(
                    domain = second_salesforce_domain,
                    username = second_salesforce_username,
                    password = second_salesforce_password,
                    token = second_salesforce_token
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

    # this will make logs come out as json and send logs elsewhere
    def setup_logging(self, logger=logging.getLogger(__name__)):

        class JSONFormatter(logging.Formatter):
            def __init__(self, run_id, sfpu: SalesforcePersonUpdates):
                super().__init__()
                self.run_id = run_id
                self.sfpu = sfpu

            # NOTE: do not add a logger statement in this function, it will cause an infinite loop
            def format(self, record: LogRecord) -> str:
                log_data = {
                    'run_id': self.run_id,
                    'timestamp': self.formatTime(record),
                    'level': record.levelname,
                    'message': record.getMessage(),
                    'logger': record.name,
                    'pathname': record.pathname,
                    'lineno': record.lineno
                }

                self.sfpu.push_log(message=record.getMessage(), levelname=record.levelname, datetime=None, run_id=sfpu.run_id)

                # return super().format(record)
                return json.dumps(log_data)
                                    
        # remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        stream_handler = logging.StreamHandler()
        formatter = JSONFormatter(run_id=self.run_id, sfpu=self)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        return logger

    # NOTE: do not add a logger statement in this function, it will cause an infinite loop
    def push_log(self, message, levelname, datetime, run_id, log_object="huit__Log__c"):
        data = {
            "huit__Message__c": message,
            "huit__Source__c": "HUD",
            "huit__Level__c": levelname,
            "huit__RunId__c": run_id,
            "huit__Datetime__c": datetime
        }
        try:
            response = self.hsf.sf.__getattr__(log_object).create(data)
        except Exception as e:
            raise Exception(f"Logging failed: {data} :: {e}")

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

        self.transformer.hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getSourceConfig('departments'), 
            source_data=results
        )

        # data will have the structure of { "OBJECT": [{"FIELD": "VALUE"}, ...]}
        data = {}
        data_gen = self.transformer.transform(source_data=results, source_name='departments')
        for d in data_gen:
            for i, v in d.items():
                if i not in data:
                    data[i] = []
                data[i].append(v)


        logger.debug(f"**** Push Departments to SF  ****")
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
        logger.debug(f"**** Push Contact data to SF:  {time_now}")
        for object, object_data in data.items():
            logger.debug(f"object: {object}")
            logger.debug(pformat(object_data))

            self.hsf.pushBulk(object, object_data)

        self.transformer.hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getSourceConfig('pds'), 
            source_data=people
        )


        time_now = datetime.now().strftime('%H:%M:%S')
        logger.debug(f"Starting related data: {time_now}")

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


        threads = []
        time_now = datetime.now().strftime('%H:%M:%S')
        logger.debug(f"**** Push Remaining People data to SF:  {time_now}")
        for object, object_data in data.items():
            logger.debug(f"object: {object}")
            logger.debug(pformat(object_data))

            # unthreaded:
            # self.hsf.pushBulk(object, object_data)    

            thread = threading.Thread(target=self.hsf.pushBulk, args=(object, object_data))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()

        # NOTE: see notes on this function
        # hsf.setDeleteds(object='Contact', id_type='HUDA__hud_UNIV_ID__c', deleted_flag='lastName', ids=['31598567'])

    def update_single_person(self, huids):
        pds_query = self.app_config.pds_query
        if 'conditions' not in pds_query:
            pds_query['conditions'] = {}
        pds_query['conditions']['univid'] = huids
        people = self.pds.get_people(pds_query)
        self.process_people_batch(people=people)

    def update_people_data_load(self, watermark: datetime=None):
        if not watermark:
            watermark = self.app_config.watermarks['person']

        pds_query = self.app_config.pds_query
        pds_query['conditions']['updateDate'] = ">" + watermark.strftime('%Y-%m-%dT%H:%M:%S')
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

        count = 1
        current_time = datetime.now().strftime('%H:%M:%S')
        logger.debug(f"Starting batch {count}: {current_time}")

        if not dry_run:
            self.process_people_batch(people)
        logger.info(f"Finished batch {count}: {tally_count} of {total_count}")

        max_count = (total_count / size)

        while(True):
            response = self.pds.next()
            count += 1

            # this should trigger if response is None or {}, which is what happens when pagination finishes.
            if not response:
                break

            if response['total_count'] != total_count:
                logger.error(f"Something went wrong with PDS pagination. Total counts changed from {total_count} to {response['total_count']}")
                raise

            current_time = datetime.now().strftime('%H:%M:%S')
            logger.debug(f"Starting batch {count}: {current_time}")

            results = response['results']
            people = self.pds.make_people(results)
            if not dry_run:
                self.process_people_batch(people)
            current_count = response['count']

            current_time = datetime.now().strftime('%H:%M:%S')
            logger.info(f"Finished batch {count}: {tally_count} of {total_count}")
            tally_count += current_count

            if count > (max_count + 5):
                logger.error(f"Something probably went wrong with the batching. Max estimated batch number ({max_count}) exceeded.")
                raise Exception(f"estimated max_count: {max_count}, batch_size: {size}, batch number (count): {count}, total_count: {total_count}")
        
        if tally_count != total_count:
            logger.error(f"PDS failed to retrieve all records ({tally_count} != {total_count})")
            raise Exception(f"Error: PDS failed to retrieve all records")
        else:
            logger.info(f"Successfully finished data load: {self.run_id}")

    # This is not intended for much use.
    def delete_people(self, dry_run: bool=True, huids: list=[]):
        pds_query = self.app_config.pds_query
        # clear conditions
        pds_query['conditions'] = {}
        # if 'conditions' not in pds_query:
        #     pds_query['conditions'] = {}
        pds_query['conditions']['univid'] = huids

        response = self.pds.search(pds_query)
        current_count = response['count']
        size = self.pds.batch_size
        total_count = response['total_count']
        tally_count = current_count
        results = response['results']

        self.transformer.hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getSourceConfig('pds'), 
            source_data=results
        )

        

        for object_name, hashed_ids in self.transformer.hashed_ids.items():
            ids = []
            for source_id, salesforce_id in hashed_ids["Ids"].items():
                ids.append(salesforce_id)

            if not dry_run:
                self.hsf.delete_records(object_name=object_name, ids=ids)

        logger.info(f"Delete Done, I hope you meant to do that.")

    def check_updateds(self):

        # 1. Get all (external) IDs from Salesforce
        object_name = 'Contact'
        # get the external id we're using in the config for this org
        external_id = self.app_config.config['Contact']['Id']['salesforce']
        pds_id = self.app_config.config['Contact']['Id']['pds']
        all_sf_ids = self.hsf.get_all_external_ids(object_name=object_name, external_id=external_id)
        
        # 2. Call PDS with those IDs

        # we only need to know if these are getttable, 
        #   it doesn't matter what other fields or conditions are in the provided query
        pds_query = {}
        pds_query['fields'] = [pds_id]
        pds_query['conditions'] = {}
        pds_query['conditions'][pds_id] = all_sf_ids

        people = self.pds.get_people(pds_query)

        # make it a list
        all_pds_ids = []
        for person in people:
            all_pds_ids.append(person[pds_id])
        
        logger.debug(f"All PDS ids: {all_pds_ids}")

        # 3. Diff the lists

        not_updating_ids = [item for item in all_sf_ids if item not in all_pds_ids]
        not_updating_ids.append('2940935f3b990174')

        logger.info(f"These ids ({external_id}) are no longer being updated: {not_updating_ids}. These have been marked as no longer updated.")

        # 4. Mark the ones that don't show up
        self.hsf.flag_field(object_name=object_name, external_id=external_id, flag_name='huit__Updated__c', value=False, ids=not_updating_ids)

    

sfpu = SalesforcePersonUpdates()

# We don't need to set up the logging to salesforce if we're running locally
#  unless we're testing that
if not os.getenv("LOCAL"):
    logger = sfpu.setup_logging(logger=logger)

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
elif action == 'delete-people':
    sfpu.delete_people(dry_run=True, huids=person_ids)
elif action == 'mark-not-updated':
    sfpu.check_updateds()
elif action == 'compare':

    output_folder = os.getenv("output_folder", "../test_output/")

    from openpyxl import Workbook

    for person_id in person_ids:

        workbook = Workbook()

        contact_response1 = sfpu.hsf.getContactIds('HUDA__hud_UNIV_ID__c', [person_id])
        contact_ids1 = [record['Id'] for record in contact_response1['records']]
        contact_response2 = sfpu.hsf2.getContactIds('HUDA__hud_UNIV_ID__c', [person_id])
        contact_ids2 = [record['Id'] for record in contact_response2['records']]


        for object_name, object_config in sfpu.app_config.config.items():
            if object_config['source'] != 'pds':
                continue
            ref_field = object_config['Id']['salesforce']
            contact_ref = 'Contact.id'
            for field, value in object_config['fields'].items():
                if isinstance(value, str):
                    if value.startswith("sf."):
                        contact_ref = field
            data1 = sfpu.hsf.get_object_data(object_name, contact_ref, contact_ids1)
            data2 = sfpu.hsf2.get_object_data(object_name, contact_ref, contact_ids2)
            result = sfpu.hsf.compare_records(object_name=object_name, ref_field=ref_field, dataset1=data1, dataset2=data2, all=True)

            # tsv_result = sfpu.hsf.compare_to_tsv(result, f"{output_folder}{object_name}.test.tsv")
            tsv_result = sfpu.hsf.compare_to_tsv(result)

            # Select the active sheet
            # sheet = workbook.active
            title = f"{object_name}"
            sheet = workbook.create_sheet(title=title)
            
            list_result = tsv_result.split("\n")
            for lr in list_result:
                row_list = lr.split("\t")
                sheet.append(row_list)


            for column_cells in sheet.columns:
                new_column_length = max(len(str(cell.value)) for cell in column_cells)
                new_column_letter = column_cells[0].column_letter
                if new_column_length > 0:
                    sheet.column_dimensions[new_column_letter].width = new_column_length*1.23

        # remove the default sheet
        workbook.remove(workbook.active)

        # Save the workbook
        filename= f"{output_folder}{person_id}_compare_results.xlsx"
        if os.path.exists(filename):
            response = os.remove(filename)
        workbook.save(filename)


elif action == 'test':
    # this action is for testing
    logger.info("test action called")
    logger.info("done test action")

else: 
    logger.warning(f"Warning: app triggered without a valid action: {action}, please see documentation for more information.")



