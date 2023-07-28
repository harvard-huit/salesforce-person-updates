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
person_ids = json.loads(os.getenv("person_ids")) or []
####################################

class SalesforcePersonUpdates:
    def __init__(self):
        try:
            if(stack != "developer"):
                logger.info("Checking if task is already running")
                if isTaskRunning() and stack != 'developer':
                    logger.warning("WARNING: application already running")
                    exit()

            if os.getenv("LOCAL") == "True":
                self.app_config = AppConfig(id=None, table_name=None, local=True)
            else:
                self.app_config = AppConfig("huit-full-sandbox", "aais-services-salesforce-person-updates-dev")

            self.hsf = HarvardSalesforce(
                domain = self.app_config.salesforce_domain,
                username = self.app_config.salesforce_username,
                password = self.app_config.salesforce_password,
                token = self.app_config.salesforce_token,
                consumer_key = self.app_config.salesforce_token,
                consumer_secret = self.app_config.salesforce_token
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


        threads = []
        time_now = datetime.now().strftime('%H:%M:%S')
        logger.info(f"**** Push Remaining People data to SF:  {time_now}")
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

    # unfinished
    def delete_people(self, dry_run: bool=False, huids: list=[]):
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

        logger.info(f"Done")




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
elif action == 'delete-people':
    sfpu.delete_people(dry_run=True, huids=person_ids)
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
                if object_name == 'HUDA__hud_Address__c':
                    logger.info(row_list)
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


    logger.info("done test")

else: 
    logger.warn(f"Warning: app triggered without a valid action: {action}")



