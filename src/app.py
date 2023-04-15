from common import isTaskRunning, logger, stack
import pds
from salesforce import HarvardSalesforce
from transformer import SalesforceTransformer

import os
import json
if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 


#### DEV debugging section #########
from pprint import pprint, pp, pformat

f = open('../example_config.json')
testconfig = json.load(f)
f.close()

f = open('../example_pds_query.json')
testquery = json.load(f)
f.close()
####################################


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

        # TODO: GET data/watermark from dynamodb based on client (now)

        # initializing a salesforce instance
        # hsf = HarvardSalesforce(
        #     domain = 'test',
        #     username = os.getenv('SF_USERNAME'),
        #     password = os.getenv('SF_PASSWORD'),
        #     consumer_key = os.getenv('SF_CLIENT_KEY'),
        #     consumer_secret = os.getenv('SF_CLIENT_SECRET')
        # )
        hsf = HarvardSalesforce(
            domain = os.getenv('SF_DOMAIN'),
            username = os.getenv('SF_USERNAME'),
            password = os.getenv('SF_PASSWORD'),
            token = os.getenv('SF_SECURITY_TOKEN'),
        )

        # check salesforce for required objects for push and get a map of the types
        hsf.getTypeMap(testconfig.keys())


        # TODO: GET list of updated people since watermark (now)
        # pds.search({
        #     "fields": ["univid"],
        #     "conditions": {
        #         "cacheUpdateDate": ">" + watermark
        #     }
        # })
        # id_results = pds.search({
        #     "fields": ["univid"],
        #     "conditions": {
        #         "univid": "80719647"
        #     }
        # })

        # TODO: removed fields from this temporarily, should come from config
        # "fields": ["univid", "names.name"],


        query = {
            "conditions": {
                "univid": ["80719647"]
            }
        }
        # this is a list of DotMaps, which allows us to access the keys with dot notation
        people = pds.People(query=query, apikey=os.getenv("PDS_APIKEY")).people
        # for person in people:
        #     logger.info(person.names)
        #     logger.info(person.effectiveStatus.code)
        

        # GET list of people from salesforce that match the ids we got back from the pds call
        # contact_results = hsf.getContactIds(id_type='HUDA__hud_UNIV_ID__c', ids=ids)
        # hashed_contacts = {}
        # for contact in contact_results['records']:
        #     hashed_contacts[contact['HUDA__hud_UNIV_ID__c']] = contact['Id']
        
        # get a map of ids for matching
        # hashed_ids = hsf.getUniqueIds(config=testconfig, people=people)

        # data will have the structure of { "OBJECT": [{"FIELD": "VALUE"}, ...]}
        data = {}

        transformer = SalesforceTransformer(config=testconfig, hsf=hsf)
        data = transformer.transform(people)




        # transform(config=testconfig, people=people, hashed_ids=hashed_ids)


        # logger.info(pformat(data))

        # TODO: pushing _dynamic_ data through to salesforce
        # Working example: push data through to salesforce
        # object = 'HUDA__hud_Name__c'
        # data = [
        #     {
        #         'Id': 'aDm1R000000PLDgSAO',
        #         'HUDA__NAME_MIDDLE__c': 'test 4'
        #     }
        # ]
        # hsf.pushBulk(object, data)
        
        # object = 'Contact'
        # data = [
        #     {
        #         'Id': '00336000010CjErAAK',
        #         'Email': 'jazahn@gmail.com'
        #     }
        # ]
        # hsf.pushBulk(object, data)


        logger.info(f"**** Push to SF  ****")
        for object, object_data in data.items():
            logger.info(f"object: {object}")
            logger.info(pformat(object_data))
            # if isinstance(object, list):
            #     for b in object:
                    
            # hsf.pushBulk(object, object_data)    

        # NOTE: see notes on this function
        # hsf.setDeleteds(object='Contact', id_type='HUDA__hud_UNIV_ID__c', deleted_flag='lastName', ids=['31598567'])

            
    except Exception as e:
        logger.error(f"Run failed with error: {e}")
        raise e
    



main()

# hsf = HarvardSalesforce(
#     domain = os.getenv('SF_DOMAIN'),
#     username = os.getenv('SF_USERNAME'),
#     password = os.getenv('SF_PASSWORD'),
#     token = os.getenv('SF_SECURITY_TOKEN'),
# )


# response = hsf.sf.Contact.metadata()
# response = hsf.getTypeMap(objects=testconfig.keys())
# logger.info(json.dumps(response))
# logger.info(pformat(json.dumps(response)))