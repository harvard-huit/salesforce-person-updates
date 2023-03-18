from common import isTaskRunning, logger, stack
import pds
from salesforce import HarvardSalesforce

import os
from dotenv import load_dotenv
load_dotenv()     

####################################################################################################
# Main
####################################################################################################
def main():

    logger.info("Starting aais-ecs-salesforce-person-updates-feed")

    try:
        if(stack != "developer"):
            logger.info("Checking if task is already running")
            if isTaskRunning() and stack != 'developer':
                logger.warning("WARNING: application already running")
                exit()

            logger.info("hello")

        # TODO: GET data/watermark from dynamodb based on client

        # TODO: GET list of updated people since watermark

        # initializing a salesforce instance
        hsf = HarvardSalesforce(
            domain = 'test',
            username = os.getenv('SF_USERNAME'),
            password = os.getenv('SF_PASSWORD'),
            consumer_key = os.getenv('SF_CLIENT_KEY'),
            consumer_secret = os.getenv('SF_CLIENT_SECRET')
        )
        # TODO: GET list of people from salesforce
        # TODO: Compare what salesforce has to what? 

        # TODO: GET full data (based on config) for a batch from the PDS
        # for now, we'll just get one specific person's name
        pds.search({
            "fields": ["univid", "names.name"],
            "conditions": {
                "univid": "80719647"
            }
        })

        # TODO: push data through to salesforce
        object = 'HUDA__hud_Name__c'
        data = [
            {
                'Id': 'aDm1R000000PLDgSAO',
                'HUDA__NAME_MIDDLE__c': 'test 4'
            }
        ]
        hsf.pushBulk(object, data)


            
    except Exception as e:
        logger.error(f"Run failed with error: {e}")
        raise e
    



main()