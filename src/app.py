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
import math
from datetime import datetime

#### DEV debugging section #########
from pprint import pformat
import psutil

if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 

    config_filename = '../example_config.json'
    if os.getenv("CONFIG_FILENAME") is not None:
        config_filename = os.getenv("CONFIG_FILENAME")

    f = open(config_filename, 'r')
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
batch_thread_count_override = os.getenv("BATCH_THREAD_COUNT") or None
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

            logger.info(f"Starting PDC {self.action} action on: {self.salesforce_instance_id}")

            current_time_mash = datetime.now().strftime('%Y%m%d%H%M')
            self.run_id = f"{self.action}_{current_time_mash}"


            if local == "True":
                self.app_config = AppConfig(id=None, table_name=None, local=True)
            else:
                if self.salesforce_instance_id is None or self.table_name is None:
                    raise Exception("ERROR: SALESFORCE_INSTANCE_ID and TABLE_NAME are required env vars, these tell us where to get the configuration.")

                self.app_config = AppConfig(id=self.salesforce_instance_id, table_name=self.table_name)
            
            if os.getenv("FORCE_LOCAL_CONFIG"):
                self.app_config.config = config
                # self.app_config.pds_query = pds_query

            self.record_limit = None
            try:
                if int(os.getenv("RECORD_LIMIT")) > 0:
                    self.record_limit = int(os.getenv("RECORD_LIMIT"))
            except:
                pass

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

            # initialize storage for updated ids
            self.updated_ids = []

            # self.pds_apikey = os.getenv("PDS_APIKEY")
            # initialize pds
            if batch_size_override:
                batch_size = int(batch_size_override)
            else:
                batch_size = 500
            self.pds = pds.People(apikey=self.app_config.pds_apikey, batch_size=batch_size)

            if batch_thread_count_override:
                self.batch_thread_count = int(batch_thread_count_override)
            else:
                self.batch_thread_count = 3
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

    def setup_department_hierarchy(self, 
                                   department_hash: dict, 
                                   external_id: str, 
                                   code_field: str, 
                                   description_field: str):
        """
        NOTE on simplifying codes: we had to do this because codes are more than 10 characters and the current id field is 
          limited to 10 characters

        This is hard-coded. The configuration needs to be put in the config file.
        """
        logger.info(f"Starting department hierarchy setup")


        # get the record type ids for Account
        account_record_type_ids = self.hsf.get_record_type_ids('Account')

        logger.info(f"account record type ids: {account_record_type_ids}")

        try:
            if not self.departments:
                self.departments = Departments(apikey=self.app_config.dept_apikey)

            if 'hierarchy' not in self.app_config.config['Account']:
                raise Exception(f"Error: hierarchy config not found in Account config")
            
            simplify_codes = False
            if 'simplify_codes' in self.app_config.config['Account']['hierarchy']:
                simplify_codes = self.app_config.config['Account']['hierarchy']['simplify_codes']

            # check length of the external id
            account_type_map = self.hsf.getTypeMap(['Account'])
            if external_id not in account_type_map['Account']:
                raise Exception(f"Error: external_id {external_id} not found in Account Object")
            if account_type_map['Account'][external_id]['externalId'] is False:
                raise Exception(f"Error: external_id {external_id} is not an external id")
            if code_field not in account_type_map['Account']:
                raise Exception(f"Error: code_field {code_field} not found in Account Object")
            if description_field not in account_type_map['Account']:
                raise Exception(f"Error: description_field {description_field} not found in Account Object")
            if account_type_map['Account'][external_id]['length'] < 10:
                raise Exception(f"Error: external_id {external_id} is too short ({account_type_map['Account'][external_id]['length']} characters)")
            if account_type_map['Account'][external_id]['length'] >= 20:
                # if it's long enough, we don't need to simplify the codes
                simplify_codes = False

            simplified_codes = []
            major_affiliations_map = self.departments.get_major_affiliations(department_hash)
            data = []
            for code, affiliation in major_affiliations_map.items():
                description = affiliation['description']
                simplified_code = code
                if simplify_codes:
                    simplified_code = self.departments.simplify_code(code)
                    if not simplified_code:
                        raise Exception(f"Error: code failed to simplify: {code}")
                if simplified_code in simplified_codes:
                    raise Exception(f"Duplicate simplified major affiliation code found: {simplified_code} ({code})")
                simplified_codes.append(simplified_code)

                data_obj = {
                    'Name': description,
                    external_id: simplified_code,
                    code_field: code,
                    description_field: description
                }

                if 'Major Affiliation' in account_record_type_ids.keys():
                    record_type_id = account_record_type_ids['Major Affiliation']
                    data_obj['RecordTypeId'] = record_type_id

                # push major affiliations into salesforce
                data.append(data_obj)
            logger.info(f"Pushing {len(data)} major affiliations")
            self.hsf.pushBulk('Account', data, id_name=external_id)

            sub_affiliations_map = self.departments.get_sub_affiliations(department_hash)
            data = []
            for code, affiliation in sub_affiliations_map.items():
                
                simplified_code = code
                description = affiliation['description']
                parent_code = affiliation['parent_code']
                simplified_parent_code = parent_code

                if simplify_codes:
                    simplified_code = self.departments.simplify_code(code)
                    if not simplified_code:
                        raise Exception(f"Error: code failed to simplify: {code}")
                    simplified_parent_code = self.departments.simplify_code(parent_code)
                    if not simplified_parent_code:
                        raise Exception(f"Error: parent code failed to simplify: {parent_code}")
                if simplified_code in simplified_codes:
                    raise Exception(f"Duplicate simplified sub affiliation code found: {simplified_code} ({code})")
                simplified_codes.append(simplified_code)

                data_obj = {
                    'Name': description,
                    external_id: simplified_code,
                    'Parent': {
                        external_id: simplified_parent_code
                    },
                    code_field: code,
                    description_field: description
                }
                if 'Sub Affiliation' in account_record_type_ids.keys():
                    record_type_id = account_record_type_ids['Sub Affiliation']
                    data_obj['RecordTypeId'] = record_type_id

                # push sub affiliations into salesforce
                data.append(data_obj)

            logger.info(f"Pushing {len(data)} sub affiliations")
            self.hsf.pushBulk('Account', data, id_name=external_id, retries=1)
            return True
        except Exception as e:
            logger.error(f"Error in building Account Hierarchy: {e}")
            return False
        # logger.debug(simplified_codes)

    # valid types are "full" and "update"
    def departments_data_load(self, type="full", hierarchy=False):
        logger.info(f"Starting a department {type} load")
        self.departments = Departments(apikey=self.app_config.dept_apikey)


        hashed_departments = self.departments.department_hash
        logger.debug(f"Successfully got {len(self.departments.results)} departments")

        record_type_ids = self.hsf.get_record_type_ids('Account')

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

        external_id = self.app_config.config['Account']['Id']['salesforce']
        if hierarchy:
            code_field = self.app_config.config['Account']['hierarchy']['code_field']
            description_field = self.app_config.config['Account']['hierarchy']['description_field']
            self.setup_department_hierarchy(department_hash=hashed_departments, external_id=external_id, code_field=code_field, description_field=description_field)


        # data will have the structure of { "OBJECT": [{"FIELD": "VALUE"}, ...]}
        data = {}
        data_gen = self.transformer.transform(source_data=results, source_name='departments')
        for d in data_gen:
            for i, v in d.items():
                if i not in data:
                    data[i] = []
                if 'Harvard Department' in record_type_ids.keys():
                    v['RecordTypeId'] = record_type_ids['Harvard Department']
                data[i].append(v)


        logger.debug(f"**** Push Departments to SF  ****")
        for object, object_data in data.items():
            logger.debug(f"object: {object}")
            logger.debug(pformat(object_data))

            self.hsf.pushBulk(object, object_data, id_name=external_id)

        self.app_config.update_watermark("department")
        logger.info(f"Department Watermark updated: {watermark}")
        logger.info(f"Finished department {type} load")

    def process_people_batch(self, people: list=[]):

        hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getTargetConfig('Contact'), 
            source_data=people
        )
        # this will overwrite the existing hashed_ids
        if 'Contact' in self.transformer.hashed_ids:
            self.transformer.hashed_ids['Contact'] = hashed_ids['Contact']

        if 'Contact' in self.app_config.config:
            logger.info(f"Processing {len(people)} Contact records")
            data = {}
            data_gen = self.transformer.transform(source_data=people, target_object='Contact')
            for d in data_gen:
                for i, v in d.items():
                    if i not in data:
                        data[i] = []
                    if 'updatedFlag' in self.app_config.config[i]:
                        updated_flag = self.app_config.config[i]['updatedFlag']
                        v[updated_flag] = True
                    data[i].append(v)

            contact_external_id = self.app_config.config['Contact']['Id']['salesforce']
            for object, object_data in data.items():
                logger.debug(f"Upserting to {object} with {len(object_data)} records")
                self.hsf.pushBulk(object, object_data, id_name=contact_external_id)


        hashed_ids = self.hsf.getUniqueIds(
            config=self.transformer.getSourceConfig('pds'), 
            source_data=people
        )
        # this will overwrite the existing hashed_ids
        for object_name in hashed_ids.keys():
            self.transformer.hashed_ids[object_name] = hashed_ids[object_name]

        data = {}
        # data is a dict where the keys are the object names and the values are lists of records

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
                        
        del data_gen

        self.push_records(data=data)
        data = {}

    def push_records(self, data: dict):
        # this will push each object's data to Salesforce in a separate thread
        # the data is a dict where the keys are the object names and the values are lists of records
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

    def update_single_person(self, huids):
        pds_query = self.app_config.pds_query
        # if 'conditions' not in pds_query:
        pds_query['conditions'] = {}
        pds_query['conditions']['univid'] = huids
        # people = self.pds.get_people(pds_query)

        # self.process_people_batch(people=people)

        self.people_data_load(pds_query=pds_query)
        
        if len(self.batch_threads) > 0:
            logger.debug(f"Waiting for batch jobs to finish.")	
            while(self.batch_threads):	
                for thread in self.batch_threads.copy():	
                    if not thread.is_alive():	
                        self.batch_threads.remove(thread)


        logger.info(f"Finished spot data load: {self.run_id}")

    def update_people_data_load(self, watermark: datetime=None, existing_only=False):
        if not watermark:
            watermark = self.app_config.watermarks['person']

        logger.info(f"Processing updates since {watermark}")

        pds_query = self.app_config.pds_query
        pds_query['conditions']['updateDate'] = ">" + watermark.strftime('%Y-%m-%dT%H:%M:%S')
        if existing_only:
            # This will limit all updates to only those that already exist in Salesforce
            updated_ids = self.hsf.get_all_external_ids(object_name='Contact', external_id=self.app_config.config['Contact']['Id']['salesforce'])
            pds_query['conditions'][self.app_config.config['Contact']['Id']['pds']] = updated_ids
        self.people_data_load(pds_query=pds_query)

        watermark = self.app_config.update_watermark("person")
        logger.info(f"Watermark updated: {watermark}")

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
        #   (update): 2 and 3 have been further mitigated by the addition of async pagination and memory management in the pds lib
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
            current_count = 0
            batch_count = 1
            max_count = math.ceil(total_count / size)

            logger.info(f"batch: {size}, total_count: {total_count}, max_count: {max_count}")

            while True:

                results = self.pds.next_page_results()

                if len(results) < 1:
                    break
                people = self.pds.make_people(results)

                # check memory usage
                memory_use_percent = psutil.virtual_memory().percent  # percentage of memory use
                # memory_avail = psutil.virtual_memory().available * 0.000001  # memory available in MB
                # memory_total = psutil.virtual_memory().total * 0.000001

                # this will get the current backlog of pds results
                current_pds_backlog = self.pds.result_queue.qsize() * self.pds.batch_size
                logger.info(f"Memory usage: {memory_use_percent}%  current pds backlog: {current_pds_backlog}/{self.pds.max_backlog} pds records {current_count}/{self.pds.total_count}")
                
                if stack != "developer":
                    if (memory_use_percent > 50) and not LOCAL:
                        time.sleep(60)
                        memory_use_percent = psutil.virtual_memory().percent  # percentage of memory use

                    if (memory_use_percent > 55) and not LOCAL:
                        raise Exception(f"Out of memory ({memory_use_percent}).")
                
                if total_count != self.pds.total_count:
                    raise Exception(f"total_count changed from {total_count} to {self.pds.total_count}. The PDS pagination failed.")

                current_count += len(results)
                if self.record_limit:
                    if current_count > self.record_limit:
                        logger.info(f"Record limit reached: {self.record_limit}")
                        break

                if current_count == total_count:
                    logger.info(f"Finished getting all records from the PDS: {total_count} records")
                elif current_count > total_count:
                    logger.warning(f"Count exceeds total_count {current_count}/{total_count}. The PDS pagination may have failed.")
                    break
                else: 
                    logger.info(f"Starting batch {batch_count}: {current_count}/{total_count} ({len(self.batch_threads)} threads in process).")
                    batch_count += 1
                    if batch_count > (max_count + 50):
                        logger.error(f"Something may have wrong with the batching. Max estimated batch count ({max_count}) exceeded current batch count: {batch_count}")
                        raise Exception(f"estimated max_count: {max_count}, batch_size: {size}, batch_count: {batch_count}, total_count: {total_count}")

                if not dry_run:
                    # self.process_people_batch(people)
                    logger.info(f"Starting a process thread")
                    thread = threading.Thread(target=self.process_people_batch, args=(people,))
                    thread.start()
                    self.batch_threads.append(thread)

                    if self.action == 'person-updates':
                        # we need a record of updated ids
                        # NOTE: v1.0.4: this may not be needed anymore since the external_id is now used more directly for the reference
                        external_id = self.app_config.config['Contact']['Ids']['pds']
                        self.updated_ids += [person[external_id] for person in people]


                    while len(self.batch_threads) >= self.batch_thread_count:
                        time.sleep(10)
                        for thread in self.batch_threads.copy():
                            # logger.info(f"{len(self.batch_threads)} unresolved threads")
                            if not thread.is_alive():
                                self.batch_threads.remove(thread)

                else:
                    logger.info(f"dry_run active: No processing happening.")


                # this will close off threads that are done, once closed, the threads will be able to bubble logs up
                for thread in self.batch_threads.copy():
                    if not thread.is_alive():
                        self.batch_threads.remove(thread)

            
                if current_count >= total_count:
                    break

            # get current timestamp
            current_time = datetime.now()
            reasonable_duration = 60 * 60 * 2 # 2 hours
            if len(self.batch_threads) > 0:
                logger.info(f"Finishing remaining processing threads: {len(self.batch_threads)}")
            while(self.batch_threads):
                if (datetime.now() - current_time).total_seconds() > reasonable_duration:
                    raise Exception(f"Something went wrong with the processing. It took too long.")
                for thread in self.batch_threads.copy():
                    if not thread.is_alive():
                        self.batch_threads.remove(thread)


        except Exception as e:
            logger.error(f"Something went wrong with the processing. ({e})")
            self.pds.wait_for_pagination()
            raise

        # while(self.batch_threads):
        #     for thread in self.batch_threads.copy():
        #         if not thread.is_alive():
        #             self.batch_threads.remove(thread)

        if len(self.batch_threads) > 0:
            logger.info(f"Waiting for batch jobs to finish.")	
            while(self.batch_threads):	
                for thread in self.batch_threads.copy():	
                    if not thread.is_alive():	
                        self.batch_threads.remove(thread)


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

    def check_for_defunct_accounts(self):
        # get all accounts that have our external id
        external_id = self.app_config.config['Account']['Id']['salesforce']
        result = self.hsf.sf.query_all(f"SELECT Id, {external_id}, LastModifiedDate FROM Account WHERE {external_id} != null ORDER BY LastModifiedDate DESC")

        ids_to_remove = []
        seen_external_ids = []
        for record in result['records']:
            if record[external_id] in seen_external_ids:
                ids_to_remove.append(record['Id'])
            else:
                seen_external_ids.append(record[external_id])

        # logger.info(f"{ids_to_remove}")
        logger.info(f"Found {len(ids_to_remove)} accounts")
        return ids_to_remove

    def remove_defunct_accounts(self):
        ids_to_remove = self.check_for_defunct_accounts()


        self.hsf.delete_records(object_name='Account', ids=ids_to_remove)
        # delete them
        # if len(ids_to_remove) > 0:
        #     logger.warning(f"Deleting {len(ids_to_remove)} accounts")
        #     ids = [{'Id': id} for id in ids_to_remove]

        #     result = self.hsf.sf.bulk.Account.delete(ids)
        #     logger.info(f"{result}")

        logger.info(f"remove_defunct_accounts action finished")
            
    def check_for_defunct_contacts(self):
        # get all contacts that have our external id
        external_id = self.app_config.config['Contact']['Id']['salesforce']
        result = self.hsf.sf.query_all(f"SELECT Id, {external_id}, LastModifiedDate FROM Contact WHERE {external_id} != null ORDER BY LastModifiedDate DESC")

        ids_to_remove = []
        seen_external_ids = []
        for record in result['records']:
            if record[external_id] in seen_external_ids:
                ids_to_remove.append(record['Id'])
            else:
                seen_external_ids.append(record[external_id])

        # logger.info(f"{ids_to_remove}")
        logger.info(f"Found {len(ids_to_remove)} contacts")
        return ids_to_remove

    def remove_defunct_contacts(self):
        ids_to_remove = self.check_for_defunct_contacts()


        self.hsf.delete_records(object_name='Contact', ids=ids_to_remove)

        logger.info(f"remove_defunct_contacts action finished")

    def get_all_updated_people(self, watermark=None) -> list:
        # get all updates ids from the pds
        pds_query = self.app_config.pds_query
        pds_id_name = self.app_config.config['Contact']['Id']['pds']
        pds_query['fields'] = [pds_id_name]
        if not watermark:
            watermark = self.app_config.watermarks['person']

        pds_query['conditions']['updateDate'] = ">" + watermark.strftime('%Y-%m-%dT%H:%M:%S')
        people = self.pds.get_people(pds_query)

sfpu = SalesforcePersonUpdates(local=LOCAL)

# We don't need to set up the logging to salesforce if we're running locally
#  unless we're testing that
if not os.getenv("SIMPLE_LOGS"):
    logger = sfpu.setup_logging(logger=logger)

# this is poorly named, I know, don't @ me
#  it's just a way to force the config to be set to the example config 
#  (while getting the rest of the env vars from dynamo)
if os.getenv("FORCE_LOCAL_CONFIG"):
    sfpu.app_config.config = config
    # sfpu.app_config.pds_query = pds_query

if action == 'single-person-update' and len(person_ids) > 0:
    sfpu.update_single_person(person_ids)
elif action == 'full-person-load':
    sfpu.full_people_data_load()
elif action == 'person-updates':
    sfpu.update_people_data_load()
elif action == 'person-updates-existing-only':
    sfpu.update_people_data_load(existing_only=True)
elif action == 'full-department-load':
    hierarchy = False
    if 'hierarchy' in sfpu.app_config.config['Account']:
        hierarchy = True
    sfpu.departments_data_load(type="full", hierarchy=hierarchy)
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
elif action == 'clean-branches':
    logger.info(f"clean-branches action called")
    
    object_id_map = {
        'HUDA__hud_Name__c': 'HUDA__PERSON_NAMES_KEY__c',
        'HUDA__hud_Email__c': 'HUDA__CONTACT_EMAIL_ADDRESS_KEY__c',
        'HUDA__hud_Phone__c': 'HUDA__CONTACT_DATA_KEY__c',
        'HUDA__hud_Address__c': 'HUDA__CONTACT_ADDRESS_KEY__c',
        'HUDA__hud_Location__c': 'HUDA__CONTACT_LOCATION_KEY__c',
        # 'hed__Affiliation__c': 'HUDA__hud_PERSON_ROLES_KEY__c'
    }
    for object_name in object_id_map.keys():
        logger.info(f"Cleaning up {object_name}")
        object_external_id = object_id_map[object_name]

        result = sfpu.hsf.sf.query_all(f"SELECT Id FROM {object_name} WHERE {object_external_id} = null")
        logger.info(f"Found {len(result['records'])} {object_name} records without external ids")

        # delete them
        if len(result['records']) > 0:
            logger.warning(f"Deleting {len(result['records'])} {object_name} records without external ids")
            ids = [{'Id': record['Id']} for record in result['records']]
            # result = sfpu.hsf.sf.bulk.__getattr__(object_name).delete(ids)
            # logger.info(f"{result}")

    logger.info(f"clean-branches action finished")

elif action == 'remove-all-contacts':
    logger.warning("remove-all-contacts")

    # get all unaffiliated Affiliation records
    result = sfpu.hsf.sf.query_all("SELECT Id, HUDA__hud_UNIV_ID__c FROM Contact LIMIT 10000")
    logger.warning(f"Found {len(result['records'])} Contact records")

    # if len(ids) > 0:
    #     logger.warning(f"Deleted {len(ids)} Contact records")

    # delete them
    ids = [record['HUDA__hud_UNIV_ID__c'] for record in result['records']]
    sfpu.delete_people(dry_run=True, huids=ids)    
elif action == 'notted-test':
    logger.info("notted-test action called")

    # isTaskRunning()

    # force action
    sfpu.action = 'person-updates'

    # do the updates
    sfpu.update_people_data_load()

    # we should now have updated_ids populated
    logger.info(sfpu.updated_ids)
    # not the ids
    notted_updated_ids = [f"!{id}" for id in sfpu.updated_ids]


    external_id = sfpu.app_config.config['Contact']['Ids']['pds']

    # create query
    updated_ids_query = {
        'fields': ["univid"],
        'conditions': {
            'updateDate': ">" + sfpu.app_config.watermarks['pds'].strftime('%Y-%m-%dT%H:%M:%S')
        }
    }
    updated_ids_query['conditions'][external_id] = notted_updated_ids

    # get all possible updated ids
    sfpu.pds.start_pagination(query=updated_ids_query, type='list', wait=True)

    id_list = sfpu.pds.results
    logger.info(id_list)
    id_list_string = "'" + '\',\''.join(id_list) + "'"

    # now select from Contact with this id list and if we have any hits filter list
    sf_data = sfpu.hsf.sf.query_all(f"SELECT {external_id} FROM Contact WHERE {external_id} IN({id_list_string})")

    new_id_list = []
    for record in sf_data['records']:
        new_id_list.append(record[external_id])

    



    logger.info("notted-test action finished")
elif action == "department test":
    logger.info("department test action called")

    departments = Departments(apikey=sfpu.app_config.dept_apikey)
    department_external_id_name = sfpu.app_config.config['Account']['Id']['salesforce']
    department_id_name = sfpu.app_config.config['Account']['Id']['departments']
    department_ids = [department[department_id_name] for department in departments.results]

    result = sfpu.hsf.get_accounts_hash(id_name=department_external_id_name, ids=department_ids)
    logger.info(f"Found {len(result.keys())} Account records")

    # get all maj affiliations
    major_affiliations = departments.get_major_affiliations(departments.results)

    object_data = []
    for major_affiliation in major_affiliations:
        obj = {
            'Name': major_affiliation['description'],
        }
        obj[department_external_id_name] = major_affiliation['code']
        if major_affiliation['code'] in result:
            obj['Id'] = result[major_affiliation['code']]['Id']
        object_data.append(obj)
    
    logger.info(f"Upserting to Account with {len(object_data)} records")
    sfpu.hsf.pushBulk('Account', object_data)

    # get all sub affiliations

    for department in departments.results:
        if department[department_id_name] not in result:
            logger.warning(f"Department {department[department_id_name]} not found in Salesforce")
        

    # sfpu.setup_department_hierarchy(departments)


    logger.info("department test action finished")
elif action == "defunct-accounts-check":
    logger.info(f"defunct accounts test action called")

    # sfpu.remove_defunct_accounts()
    ids = sfpu.check_for_defunct_accounts()

    exit()

    children = []
    # find children
    batch = 500
    for i in range(0, len(ids), batch):
        batch_ids = ids[i:i+batch]
        ids_string = "'" + '\',\''.join(batch_ids) + "'"
        select_statement = f"SELECT Id FROM Account WHERE ParentId IN ({ids_string})"
        sf_data = sfpu.hsf.sf.query_all(select_statement)

        for record in sf_data['records']:
            children.append(record['Id'])

    logger.info(f"Found {len(children)} children")


    # find affiliations
    affiliations = []
    batch = 500
    for i in range(0, len(ids), batch):
        batch_ids = ids[i:i+batch]
        ids_string = "'" + '\',\''.join(batch_ids) + "'"
        select_statement = f"SELECT Id FROM hed__Affiliation__c WHERE hed__Account__c IN ({ids_string})"
        sf_data = sfpu.hsf.sf.query_all(select_statement)

        for record in sf_data['records']:
            affiliations.append(record['Id'])
    
    logger.info(f"Found {len(affiliations)} affiliations")

    # clear affiliation account references
    logger.info(f"Clearing account references from affiliations")
    batch = 10000
    for i in range(0, len(affiliations), batch):
        batch_ids = affiliations[i:i+batch]
        batch_objects = []
        for id in batch_ids:
            batch_objects.append({'Id': id, 'hed__Account__c': None})
        sfpu.hsf.sf.bulk.hed__Affiliation__c.update(batch_objects)
    logger.info(f"finished clearing account references from affiliations")


    # sfpu.check_duplicates('Account', dry_run=True)

    # sfpu.departments = Departments(apikey=sfpu.app_config.dept_apikey)
    # sfpu.setup_department_hierarchy(department_hash=sfpu.departments.department_hash, external_id='HUDA__hud_DEPT_ID__c', code_field='HUDA__hud_DEPT_OFFICIAL_DESC__c', description_field='HUDA__hud_DEPT_LONG_DESC__c')

    # data = [
    # {
    #     "Name": "Harvard Busn Sch Major Affil",
    #     "HUDA__hud_DEPT_ID__c": "0BUS1",
    #     "HUDA__hud_DEPT_OFFICIAL_DESC__c": "BUS^MA",
    #     "HUDA__hud_DEPT_LONG_DESC__c": "Harvard Busn Sch Major Affil"
    # }
    # ]
    # sfpu.hsf.pushBulk('Account', data, id_name='HUDA__hud_DEPT_ID__c')

    logger.info(f"defunct accounts test action finished")
elif action == "remove people test":
    logger.info(f"remove people test action called")

    # get all contacts that have our external id
    external_id = sfpu.app_config.config['Contact']['Id']['salesforce']
    result = sfpu.hsf.sf.query_all(f"SELECT Id, {external_id} FROM Contact WHERE {external_id} != null ORDER BY LastModifiedDate DESC") 

    # delete them all (we expect this to fail for those with relationships)
    ids = [{'Id': record['Id']} for record in result['records']]
    logger.info(f"Found {len(ids)} Contact records")
    # result = sfpu.hsf.sf.bulk.Contact.delete(ids)

    logger.info(f"remove people test action finished")
elif action == "test":
    logger.info(f"test action called")

    for object_name in sfpu.app_config.config.keys():
        logger.info(f"Checking {object_name}")
        # get all records with our external id
        external_id = sfpu.app_config.config[object_name]['Id']['salesforce']
        results = sfpu.hsf.sf.query_all(f"SELECT Id, {external_id} FROM {object_name} WHERE {external_id} != null ORDER BY LastModifiedDate DESC")
        logger.info(f"Found {len(results['records'])} {object_name} records")

        this_many = 100000000
        count = 0
        ids = []
        for record in results['records']:
            # logger.info(f"{count}: {record['Id']} - {record[external_id]}")
            ids.append(record['Id'])
            count += 1
            if count >= this_many:
                break
        
        # delete them all
        ids = [{'Id': id} for id in ids]
        if len(ids) > 0:
            logger.info(f"Deleting {len(ids)} {object_name} records")
            result = sfpu.hsf.sf.bulk.__getattr__(object_name).delete(ids)



    # # get all contacts that have our external id
    # external_id = sfpu.app_config.config['Contact']['Id']['salesforce']
    # results = sfpu.hsf.sf.query_all(f"SELECT Id, {external_id} FROM Contact WHERE HUDA__hud_EPPN__c != null ORDER BY LastModifiedDate DESC")
    # logger.info(f"Found {len(results['records'])} Contact records")

    # this_many = 100000
    # count = 0
    # ids = []
    # for record in results['records']:
    #     # logger.info(f"{count}: {record['Id']} - {record[external_id]}")
    #     ids.append(record['Id'])
    #     count += 1
    #     if count >= this_many:
    #         break
    
    # # delete them all
    # ids = [{'Id': id} for id in ids]
    # logger.info(f"Deleting {len(ids)} Contact records")
    # result = sfpu.hsf.sf.bulk.Contact.delete(ids)

    logger.info(f"test action finished")
else: 
    logger.warning(f"App triggered without a valid action: {action}, please see documentation for more information.")



