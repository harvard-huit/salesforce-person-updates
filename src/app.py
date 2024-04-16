from common import isTaskRunning, setTaskRunning, logger, stack
from departments import Departments
from salesforce_person_updates import SalesforcePersonUpdates
from account_handler import AccountHandler

import os
import json
import time


import inspect
def is_unittest():
    for frame in inspect.stack():
        if 'unittest' in frame.filename:
            return True
    return False

if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 

    config_filename = '../example_config.json'
    
    if os.getenv("CONFIG_FILENAME") is not None:
        config_filename = os.getenv("CONFIG_FILENAME")

    if is_unittest():
        config_filename = '../' + config_filename

    f = open(config_filename, 'r')
    config = json.load(f)
    f.close()

    query_filename = '../example_pds_query.json'
    if is_unittest():
        query_filename = '../' + query_filename

    f = open(query_filename, 'r')
    pds_query = json.load(f)
    f.close()
####################################


#### Collect action directive ######
action = os.getenv("action", "undefined")
if os.getenv("person_ids"):
    person_ids = json.loads(os.getenv("person_ids"))
else:
    person_ids = []

pds_batch_size_override = os.getenv("PDS_BATCH_SIZE") or None
batch_size_override = os.getenv("BATCH_SIZE") or None
batch_thread_count_override = os.getenv("BATCH_THREAD_COUNT") or None
LOCAL = os.getenv("LOCAL") or False
####################################


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

task_running = isTaskRunning(sfpu.app_config)
WAIT_LIMIT = 20
if task_running and not stack == "developer":
    if action in ['single-person-update','person-updates','person-updates-updates-only','department-updates','delete-people','cleanup-updateds','remove-unaffiliated-affiliations','remove-all-contacts','department test','defunct-accounts-check','remove people test','delete-all-data']:
        logger.warning(f"The current task is actively running.")
        exit()
    elif action in ['full-person-load','full-department-load']:
        wait_count = 1
        while (task_running and wait_count <= WAIT_LIMIT):
            logger.warning(f"The current task is actively running. (Currently on try {wait_count}/{WAIT_LIMIT})")
            time.sleep(30)
            task_running = isTaskRunning(sfpu.app_config)
            wait_count += 1
        if task_running and wait_count > WAIT_LIMIT:
            logger.warning(f"The current task is actively running and the wait limit of {WAIT_LIMIT} has been exceeded.")
            exit()

setTaskRunning(sfpu.app_config, True, run_id=sfpu.run_id)

try:
    if action == 'single-person-update' and len(person_ids) > 0:
        sfpu.update_single_person(person_ids)
    elif action == 'full-person-load':
        updates_only = False
        if 'Contact' in sfpu.app_config.config and 'updateOnlyFlag' in sfpu.app_config.config['Contact'] and sfpu.app_config.config['Contact']['updateOnlyFlag'] == True:
            updates_only = True

        # disabling updates_ony for now
        updates_only = False

        sfpu.full_people_data_load(updates_only=updates_only)

    elif action == 'person-updates':
        updates_only = False
        if 'Contact' in sfpu.app_config.config and 'updateOnlyFlag' in sfpu.app_config.config['Contact'] and sfpu.app_config.config['Contact']['updateOnlyFlag'] == True:
            updates_only = True
        
        # disabling updates_ony for now
        updates_only = False

        sfpu.update_people_data_load(updates_only=updates_only)
    elif action == 'full-department-load':
        hierarchy = False
        if 'hierarchy' in sfpu.app_config.config['Account']:
            hierarchy = True
        sfpu.departments_data_load(type="full", hierarchy=hierarchy)
    elif action == 'department-updates':
        sfpu.departments_data_load(type="update")
    elif action == 'delete-people':
        sfpu.delete_people(dry_run=True, huids=person_ids)
    elif action == 'cleanup-updateds':
        sfpu.cleanup_updateds()
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
        logger.warning("remove-all-contacts")

        # get all unaffiliated Affiliation records
        result = sfpu.hsf.sf.query_all("SELECT Id, HUDA__hud_UNIV_ID__c FROM Contact LIMIT 10000")
        logger.warning(f"Found {len(result['records'])} Contact records")

        # if len(ids) > 0:
        #     logger.warning(f"Deleted {len(ids)} Contact records")

        # delete them
        ids = [record['HUDA__hud_UNIV_ID__c'] for record in result['records']]
        sfpu.delete_people(dry_run=True, huids=ids)    
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
    elif action == "delete-all-data":
        logger.warning(f"delete-all-data action called")
        for object_name in sfpu.app_config.config.keys():
            logger.info(f"{object_name}")
            external_id = sfpu.app_config.config[object_name]['Id']['salesforce']
            result = sfpu.hsf.sf.query_all(f"SELECT Id, {external_id} FROM {object_name} WHERE {external_id} != null ORDER BY LastModifiedDate DESC")
            logger.info(f"Found {len(result['records'])} {object_name} records")
            # delete them all
            ids = [{'Id': record['Id']} for record in result['records']]
            logger.warning(f"attempting delete")
            # sfpu.hsf.sf.bulk.__getattr__(object_name).delete(ids)
            logger.warning(f"delete complete")

        logger.info(f"delete-all-data action finished")
    elif action == "static-query":
        logger.info(f"static-query action called")
        # query_filename = '../examples/example_pds_query_hms.json'
        # f = open(query_filename, 'r')
        # pds_query = json.load(f)
        # f.close()
        pds_query = sfpu.app_config.pds_query
        pds_query['conditions'] = {
            "cacheUpdateDate": "2024-02-14T05:00:00>2024-02-16T16:30:00"
        }
        sfpu.people_data_load(pds_query=pds_query)

        logger.info(f"static-query action finished")
    elif action == "full-account-load":
        logger.info(f"full-account-load action called")

        account_handler = AccountHandler(sfpu)
        account_handler.accounts_data_load()

        logger.info(f"full-account-load action finished")
    elif action == "test":
        logger.info(f"test action called")

        result = sfpu.hsf.validateConfig(config=sfpu.app_config.config)
        logger.info(f"Config validation result: {result}")

        logger.info(f"test action finished")
    else: 
        logger.warning(f"App triggered without a valid action: {action}, please see documentation for more information.")
except Exception as e:
    logger.error(e)
finally:
    setTaskRunning(sfpu.app_config, False, run_id=sfpu.run_id)
