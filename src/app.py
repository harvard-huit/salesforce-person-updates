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
import time
from datetime import datetime

import requests

#### DEV debugging section #########
from pprint import pformat

if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 

    f = open('../example_config.json')
    config = json.load(f)
    f.close()

    f = open('../example_pds_query.json')
    pds_query = json.load(f)
    f.close()
####################################


#### Collect action directive ######
action = os.getenv("action", "undefined")
if os.getenv("person_ids"):
    person_ids = json.loads(os.getenv("person_ids"))
else:
    person_ids = []

batch_size_override = os.getenv("BATCH_SIZE") or None
LOCAL = os.getenv("LOCAL") or False
####################################

class SalesforcePersonUpdates:
    def __init__(self, local=False):
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

            self.action = os.getenv("action", None)

            current_time_mash = datetime.now().strftime('%Y%m%d%H%M')
            self.run_id = f"{self.action}_{current_time_mash}"


            if local == "True":
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
            if batch_size_override:
                batch_size = int(batch_size_override)
            else:
                batch_size = 500
            self.pds = pds.People(apikey=self.app_config.pds_apikey, batch_size=batch_size)
            # self.pds_thread = 

            self.batch_threads = []

            self.transformer = SalesforceTransformer(config=self.app_config.config, hsf=self.hsf)




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
                    'salesforce_instance_id': self.sfpu.salesforce_instance_id,
                    'run_id': self.run_id,
                    'timestamp': self.formatTime(record),
                    'level': record.levelname,
                    'message': record.getMessage(),
                    'logger': record.name,
                    'pathname': record.pathname,
                    'lineno': record.lineno
                }

                try: 
                    self.sfpu.push_log(message=record.getMessage(), levelname=record.levelname, datetime=None, run_id=sfpu.run_id)
                except Exception as e:
                    log_data['log_error'] = str(e)

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
        self.departments = Departments(apikey=self.app_config.dept_apikey)

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

        logger.info(f"Processing {len(people)} Contact records")
        data = {}
        data_gen = self.transformer.transform(source_data=people, target_object='Contact')
        for d in data_gen:
            for i, v in d.items():
                if i not in data:
                    data[i] = []
                data[i].append(v)


        for object, object_data in data.items():
            logger.debug(f"Upserting to {object} with {len(object_data)} records")
            self.hsf.pushBulk(object, object_data)

        self.transformer.hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getSourceConfig('pds'), 
            source_data=people
        )

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

        branch_threads = []

        for object, object_data in data.items():
            logger.debug(f"Upserting to {object} with {len(object_data)} records")

            # unthreaded:
            # self.hsf.pushBulk(object, object_data)    

            thread = threading.Thread(target=self.hsf.pushBulk, args=(object, object_data))
            thread.start()
            branch_threads.append(thread)
        
        # it's okat to join them all here as this will generally be done in a sub-thread, 
        #   so they won't block the main thread
        for thread in branch_threads:
            thread.join()

        # for thread in self.threads.copy():
        #     if not thread.is_alive():
        #         self.threads.remove(thread)

    def update_single_person(self, huids):
        pds_query = self.app_config.pds_query
        if 'conditions' not in pds_query:
            pds_query['conditions'] = {}
        pds_query['conditions']['univid'] = huids
        # people = self.pds.get_people(pds_query)

        # self.process_people_batch(people=people)

        self.people_data_load(pds_query=pds_query)

        logger.info(f"Finished spot data load: {self.run_id}")

    def update_people_data_load(self, watermark: datetime=None):
        logger.info(f"Processing updates since {watermark}")
        if not watermark:
            watermark = self.app_config.watermarks['person']

        pds_query = self.app_config.pds_query
        pds_query['conditions']['updateDate'] = ">" + watermark.strftime('%Y-%m-%dT%H:%M:%S')
        self.people_data_load(pds_query=pds_query)

        self.app_config.update_watermark("person")

    def full_people_data_load(self, dry_run=False):
        logger.info(f"Processing full data load")

        try:
            self.people_data_load(dry_run=dry_run)

            logger.debug(f"Waiting for batch jobs to finish.")
            while(self.batch_threads):
                #  logger.info(f"{len(self.batch_threads)} remaining threads")
                for thread in self.batch_threads.copy():
                    if not thread.is_alive():
                        self.batch_threads.remove(thread)

            self.app_config.update_watermark("person")
            logger.info(f"Finished full data load: {self.run_id}")
        except Exception as e:
            logger.error(f"Error with full data load")
            raise e

    def people_data_load(self, dry_run=False, pds_query=None):
        # This method creates a thread for each batch, this may seem like a lot, but it is necessitated by the following factors:
        #   1. If we rely on the async of a bulk push, we cannot get the results (created/updated/error results)
        #      (as I was unable to get the API to return results. If this changes in the future, we could rethink that)
        #      Without the results, we cannot resolve duplicate errors or have good logging
        #   2. It needs to be async in some way to make sure the PDS pagination timeout does not happen
        #   3. If we collect results and THEN process, that is too memory intensive and requires sizing up the instance
        # NOTE: we don't allow more than 3 parent threads to run at a time
        #       and the max bulk load jobs Salesforce will handle at once is 5.
        #       Some batch jobs will take an excessively long time (20 minutes) most will take 30 seconds.
        logger.debug(f"Starting data load")

        # without the pds_query, it uses the "full" configured query
        if pds_query is None:
            pds_query = self.app_config.pds_query


        try:
            self.pds.start_pagination(pds_query)
            size = self.pds.batch_size
            total_count = self.pds.total_count
            batch_count = 1
            max_count = (total_count / size)


            while True:
                tally_count = self.pds.count
                logger.info(f"Starting batch {batch_count}: {tally_count} of {total_count}")
                results = self.pds.next_page_results()
                people = self.pds.make_people(results)

                if total_count != self.pds.total_count:
                    raise Exception(f"total_count changed from {total_count} to {self.pds.total_count}. The PDS pagination failed.")

                logger.info(f"Starting batch {batch_count}: {tally_count} of {total_count} ({len(self.batch_threads)} threads in process).")

                if len(results) < 1 and not self.pds.is_paginating:
                    logger.info(f"Finished getting all records from the PDS")
                    break
                else: 
                    batch_count += 1
                    if batch_count > (max_count + 5):
                        logger.error(f"Something probably went wrong with the batching. Max estimated batch number ({max_count}) exceeded.")
                        raise Exception(f"estimated max_count: {max_count}, batch_size: {size}, batch_count: {batch_count}, total_count: {total_count}")


                if not dry_run:
                    # self.process_people_batch(people)
                    thread = threading.Thread(target=self.process_people_batch, args=(people,))
                    thread.start()
                    self.batch_threads.append(thread)

                    while len(self.batch_threads) >= 3:
                        time.sleep(10)
                        for thread in self.batch_threads.copy():
                            # logger.info(f"{len(self.batch_threads)} unresolved threads")
                            if not thread.is_alive():
                                self.batch_threads.remove(thread)


                # this will close off threads that are done, once closed, the threads will be able to bubble logs up
                for thread in self.batch_threads.copy():
                    if not thread.is_alive():
                        self.batch_threads.remove(thread)

            logger.info(f"Finishing remaining processing threads: {len(self.batch_threads)}")
            while(self.batch_threads):
                for thread in self.batch_threads.copy():
                    if not thread.is_alive():
                        self.batch_threads.remove(thread)


        except Exception as e:
            logger.error(f"Something went wrong with the processing.")
            self.pds.wait_for_pagination()

        logger.info(f"Successfully finished data load: {self.run_id}")



    # This is intended for debug use only.
    # We should not be deleting any records.
    def delete_people(self, dry_run: bool=True, huids: list=[]):
        pds_query = self.app_config.pds_query
        # clear conditions
        pds_query['conditions'] = {}
        pds_query['conditions']['univid'] = huids

        response = self.pds.search(pds_query)
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

        logger.warning(f"Delete Done, I hope you meant to do that.")

    def check_updateds(self):

        logger.info(f"Checking PDS for records that are no longer being updated")

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

        logger.info(f"These ids ({external_id}) are no longer being updated: {not_updating_ids}. These have been marked as no longer updated.")

        # 4. Mark the ones that don't show up
        self.hsf.flag_field(object_name=object_name, external_id=external_id, flag_name='huit__Updated__c', value=False, ids=not_updating_ids)

    # this method will create xls files with comparisons of data from 2 salesforce sources
    # it can only really be run locally and also requires a second set of salesforce credentials
    # it isn't well fleshed out, but it works
    # What makes it helpful for testers is to have the output_folder set to something that is mapped to Sharepoint
    def compare_records(self):
        logger.info(f"Comparing records: {person_ids}")
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


    

sfpu = SalesforcePersonUpdates(local=LOCAL)

# We don't need to set up the logging to salesforce if we're running locally
#  unless we're testing that
if not os.getenv("SIMPLE_LOGS"):
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
    sfpu.compare_records()

elif action == 'remove-unaffiliated-affiliations':
    logger.info("remove-unaffiliated-affiliations action called")

    # get all unaffiliated Affiliation records
    result = sfpu.hsf.sf.query_all("SELECT Id FROM hed__Affiliation__c WHERE hed__Contact__c = null and HUDA__hud_PERSON_ROLES_KEY__c != null")
    logger.info(f"Found {len(result['records'])} unaffiliated Affiliation records")

    # delete them
    ids = [{'Id': record['Id']} for record in result['records']]
    sfpu.hsf.sf.bulk.hed__Affiliation__c.delete(ids)

    if len(ids) > 0:
        logger.warning(f"Deleted {len(ids)} unaffiliated Affiliation records")
elif action == 'remove-all-contacts':
    logger.info("remove-all-contacts")

    # get all unaffiliated Affiliation records
    result = sfpu.hsf.sf.query_all("SELECT Id, HUDA__hud_UNIV_ID__c FROM Contact LIMIT 10000")
    logger.info(f"Found {len(result['records'])} Contact records")

    # if len(ids) > 0:
    #     logger.warning(f"Deleted {len(ids)} Contact records")

    # delete them
    ids = [record['HUDA__hud_UNIV_ID__c'] for record in result['records']]
    sfpu.delete_people(dry_run=False, huids=ids)    


elif action == 'test':
    logger.info("test action called")

    # isTaskRunning()

    logger.info("test action finished")
else: 
    logger.warning(f"App triggered without a valid action: {action}, please see documentation for more information.")



