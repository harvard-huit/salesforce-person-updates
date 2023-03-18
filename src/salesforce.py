import requests
import os
import json
from urllib.parse import urlencode
from simple_salesforce import Salesforce 

from common import logger

class HarvardSalesforce:
    def __init__(self, domain, username, password, consumer_key, consumer_secret):
        self.domain = domain
        self.username = username
        try: 
            logger.info(f"initializing to {self.domain} as {self.username}")
            self.sf = Salesforce(
                username=self.username,
                password=password,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                domain=self.domain
            )
        except Exception as e:
            logger.error(f"error connecting to salesforce: {e}")
            raise e

    # NOTE: this uses the Salesforce Bulk API
    # this API is generally async, but the way I'm using it, it will wait (synchronously) for the job to finish 
    # that will probably be too slow to do fully sync
    # to make best use of this, we will need to async it with something like asyncio
    # NOTE: the Bulk API can take a max of 10000 records at a time
    # a single record will take anywhere from 2-50 seconds
    def pushBulk(self, object, data):
        logger.info(f"pushBulk to {object} with {data}")

        responses = self.sf.bulk.__getattr__(object).upsert(data, external_id_field='Id')
        logger.info(responses)
        for response in responses:
            if response['success'] != True:
                logger.error(f"Error in bulk data load: {response['errors']}")
                return False
        return True
    
    def getContactIds(huids):
        logger.info(f"getContactIds with the following huids: {huids}")



################### OLD but working code below ##############

def initialize():
    domain = 'test'
    username = os.getenv('SF_USERNAME')
    try: 
        logger.info(f"initializing to {domain} as {username}")
        sf = Salesforce(
            username=username,
            password=os.getenv('SF_PASSWORD'),
            consumer_key=os.getenv('SF_CLIENT_KEY'),
            consumer_secret=os.getenv('SF_CLIENT_SECRET'),
            domain=domain
        )
        return sf
    except Exception as e:
        logger.error(f"error connecting to salesforce: {e}")
        raise e


def sampleCall():
    try: 
        sf = initialize()

        # logger.info("trying to connect...")
        # sf = Salesforce(
        #     username=os.getenv('SF_USERNAME'),
        #     password=os.getenv('SF_PASSWORD'),
        #     consumer_key=os.getenv('SF_CLIENT_KEY'),
        #     consumer_secret=os.getenv('SF_CLIENT_SECRET'),
        #     domain='test'
        # )

        # logger.info("trying a query...")
        # sf_data = sf.query_all("SELECT Contact.id, HUDA__hud_MULE_UNIQUE_PERSON_KEY__c FROM Contact WHERE HUDA__hud_MULE_UNIQUE_PERSON_KEY__c = '88f5b068222b1f0c'")
        # logger.info(sf_data)
        # sf_data = sf.query_all("SELECT FIELDS(ALL) FROM HUDA__hud_Email__c WHERE HUDA__MULE_UNIQUE_PERSON_KEY__c = '88f5b068222b1f0c' LIMIT 200")
        # logger.info(sf_data)

        # logger.info("trying a get...")
        # contact = sf.Contact.get_by_custom_id('HUDA__hud_MULE_UNIQUE_PERSON_KEY__c', '88f5b068222b1f0c')
        # logger.info(contact)
        names = sf.HUDA__hud_Name__c.get_by_custom_id('HUDA__MULE_UNIQUE_PERSON_KEY__c', '88f5b068222b1f0c')
        # logger.info(json.dumps(names))
        names = json.loads(json.dumps(names))
        logger.info(names)

        # 88f5b068222b1f0c
        logger.info("trying an upsert...")
        data = [
            {
                'Id': 'aDm1R000000PLDgSAO',
                'HUDA__NAME_MIDDLE__c': 'test'
            }
        ]
        sf.bulk.HUDA__hud_Name__c.upsert(data, external_id_field='Id')
        # sf.bulk.__getattr__('HUDA__hud_Name__c').upsert(data, external_id_field='Id')
        
    except Exception as e:
        logger.error(f"error connecting to salesforce: {e}")
        raise e
    

# NOTE: this does not work, not sure I need it though
def getBulkLogs():
    job_logs = sf.bulk.get_all_jobs()
    most_recent_job_log = max(job_logs, key=lambda x: x['createdDate'])
    logger.info(most_recent_job_log)


# This method will work synchronously
# that will probably be too slow
# to make best use of this, we will need to async it with something like asyncio
# def pushBulk(object, data):
#     sf = initialize()
#     logger.info(f"pushBulk to {object} with {data}")
#     response = sf.bulk.__getattr__(object).upsert(data, external_id_field='Id')
#     logger.info(response)
#     if len(response['success']) == True:
#         return True
#     else:
#         logger.error(f"Error in bulk data load: {response['errors']}")
#         return False


