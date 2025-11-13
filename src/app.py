from common import isTaskRunning, setTaskRunning, logger, stack, AppConfig
from salesforce_person_updates import SalesforcePersonUpdates
from account_handler import AccountHandler

import os
import json
import time
from datetime import datetime
import pytz


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

    if os.getenv("QUERY_FILENAME") is not None:
        query_filename = os.getenv("QUERY_FILENAME")

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

stop_reason = None
try:
    sfpu = None
    sfpu = SalesforcePersonUpdates(local=LOCAL)

    # connect to salesforce


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
        if action in [
                'single-person-update',
                'validate',
                'person-updates',
                'person-updates-updates-only',
                'cleanup-updateds',
                'remove-unaffiliated-affiliations',
                'defunct-accounts-check',
                'remove people test',
                'defunct-contacts-check',
                'defunct-contacts-remove']:
            logger.warning(f"The current task is actively running.")
            exit()
        elif action in ['full-person-load','full-account-load']:
            wait_count = 1
            while (task_running and wait_count <= WAIT_LIMIT):
                logger.warning(f"The current task is actively running. (Currently on try {wait_count}/{WAIT_LIMIT})")
                time.sleep(30)
                task_running = isTaskRunning(sfpu.app_config)
                wait_count += 1
            if task_running and wait_count > WAIT_LIMIT:
                logger.warning(f"The current task is actively running and the wait limit of {WAIT_LIMIT} has been exceeded.")
                exit()

    if not stack == "developer":
        setTaskRunning(sfpu.app_config, True)

    output = ""

    if action == 'single-person-update' and len(person_ids) > 0:
        sfpu.update_single_person(person_ids)
    elif action == 'validate':
        sfpu.validate()
    elif action == 'full-person-load':
        updates_only = False
        if 'Contact' in sfpu.app_config.config and 'updateOnlyFlag' in sfpu.app_config.config['Contact'] and sfpu.app_config.config['Contact']['updateOnlyFlag'] == True:
            updates_only = True

        # disabling updates_ony for now
        updates_only = False

        sfpu.full_people_data_load(updates_only=updates_only)
        sfpu.cleanup_updateds()

    elif action == 'person-updates':
        updates_only = False
        if 'Contact' in sfpu.app_config.config and 'updateOnlyFlag' in sfpu.app_config.config['Contact'] and sfpu.app_config.config['Contact']['updateOnlyFlag'] == True:
            updates_only = True
        
        # disabling updates_ony for now
        updates_only = False

        sfpu.update_people_data_load(updates_only=updates_only)
        
        try:
            account_watermark = sfpu.app_config.watermarks.get('account', None)
            if account_watermark is not None:
                eastern = pytz.timezone('US/Eastern')
                today = datetime.now(eastern).weekday()
                accout_watermark_day = account_watermark.weekday()
                if today != accout_watermark_day:

                    account_handler = AccountHandler(sfpu)
                    account_handler.accounts_data_load()

        except Exception as e:
            logger.error(e)


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
    elif action == "defunct-accounts-check":
        logger.info(f"defunct accounts check action called")

        # sfpu.remove_defunct_accounts()
        ids = sfpu.check_for_defunct_accounts()


        logger.info(f"defunct accounts check action finished")
    elif action == "defunct-contacts-check":
        logger.info(f"defunct contacts check action called")

        ids = sfpu.check_for_defunct_contacts()

        logger.info(f"defunct contacts check action finished")
    elif action == "defunct-contacts-remove":
        logger.info(f"defunct contacts remove action called")

        sfpu.remove_defunct_contacts()

        logger.info(f"defunct contacts remove action finished")
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
        for object_name in sfpu.app_config.config.keys().reverse():
            logger.info(f"{object_name}")
            if isinstance(sfpu.app_config.config[object_name], list):
                objects = sfpu.app_config.config[object_name]
            else:
                objects = [sfpu.app_config.config[object_name]]

            for obj in objects:

                external_id = obj['Id']['salesforce']
                result = sfpu.hsf.sf.query_all(f"SELECT Id, {external_id} FROM {object_name} WHERE {external_id} != null ORDER BY LastModifiedDate DESC")
                logger.info(f"Found {len(result['records'])} {object_name} records")
                # delete them all
                ids = [{'Id': record['Id']} for record in result['records']]
                logger.warning(f"attempting delete")
                sfpu.hsf.sf.bulk.__getattr__(object_name).delete(ids)
                logger.warning(f"delete complete")

        logger.info(f"delete-all-data action finished")
    elif action == "delete-account-data":
        logger.warning(f"delete-account-data action called")
        external_id = 'Account_PDC_Key__c'
        result = sfpu.hsf.sf.query_all(f"SELECT Id, {external_id} FROM Account WHERE {external_id} != null ORDER BY LastModifiedDate DESC")
        logger.info(f"Found {len(result['records'])} Account records")
        # delete them all
        ids = [{'Id': record['Id']} for record in result['records']]
        logger.warning(f"attempting delete")
        sfpu.hsf.sf.bulk.__getattr__('Account').delete(ids)
        logger.warning(f"delete complete")

        logger.info(f"delete-account-data action finished")
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
    elif action == "duplicate-check":
        logger.info(f"duplicate-check action called")

        sfpu.check_for_duplicates()

        logger.info(f"duplicate-check action finished")
    elif action == "test":
        logger.info(f"test action called")

        logger.info(f"test action finished")
    else: 
        logger.warning(f"App triggered without a valid action: {action}, please see documentation for more information.")
    if stop_reason is None:
        stop_reason = "Success Apparent"

except Exception as e:
    action = os.getenv("action", None)
    salesforce_id = os.getenv("SALESFORCE_INSTANCE_ID", None)
    logger.error(f"Salesforce instance: {salesforce_id}, action: {action}: {e}")
    stop_reason = f"ERROR: {e}"
    raise e

finally:
    if not stack == "developer":

        action = os.getenv("action", None)
        salesforce_id = os.getenv("SALESFORCE_INSTANCE_ID", None)
        table_name = os.getenv("TABLE_NAME", None)

        if sfpu is not None:
            setTaskRunning(sfpu.app_config, False)

            logger.info(f"Salesforce instance: {salesforce_id}: Action: {action} completed. {stop_reason}")
            sfpu.app_config.stop_task_with_reason(f"Salesforce instance: {salesforce_id}: Action: {action} completed. {stop_reason}")
        else:
            app_config = AppConfig(id=salesforce_id, table_name=table_name)
            app_config.stop_task_with_reason(f"Salesforce instance: {salesforce_id}: Action: {action} completed. {stop_reason}")
