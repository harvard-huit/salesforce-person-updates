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
            
            hsf.pushBulk(object, object_data)    

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

# hsf.pushBulk("Contact", [{
#   'Birthdate': '1980-11-17',
#   'Email': 'null@harvard.edu',
#   'FirstName': 'Test',
#   'HUDA__hud_ADID__c': 'test1234',
#   'HUDA__hud_BIRTH_DT__c': '1980-11-17',
#   'HUDA__hud_DECEASED_FLAG__c': 'N',
#   'HUDA__hud_EFFDT__c': '2007-12-21T02:32:17',
#   'HUDA__hud_EFF_STATUS__c': 'A',
#   'HUDA__hud_EPPN__c': '2940935f3b990175',
#   'HUDA__hud_GENDER__c': 'M',
#   'HUDA__hud_INTERNAL_ID__c': 'e9f928bc98814859a3595494e368bbcd',
#   'HUDA__hud_MULE_UNIQUE_PERSON_KEY__c': '2940935f3b990175',
#   'HUDA__hud_UUID__c': 'e9f928bc98814859a3595494e368bbcd',
#   'LastName': 'Clevenger'
# }])


# NOTE: branches are linked to the contact record via the eppn, not the contact relationship
#       that's weird, right?
# hsf.pushBulk("HUDA__hud_Name__c", [{
#   'HUDA__EFFDT__c': '2018-10-23T02:32:49',
#   'HUDA__EFF_STATUS__c': 'A',
#   'HUDA__INTERNAL_ID__c': 'JaZahn',
#   'HUDA__MULE_UNIQUE_PERSON_KEY__c': 'acd3d0471e7ed076',
#   'HUDA__NAME_FIRST__c': 'JaZahn',
#   'HUDA__NAME_LAST__c': 'Clevenger',
#   'HUDA__NAME_MIDDLE__c': None,
#   'HUDA__NAME_PREFIX__c': None,
#   'HUDA__NAME_SUFFIX__c': None,
#   'HUDA__NAME_TYPE__c': 'LISTING',
#   'HUDA__PERSON_NAMES_KEY__c': '3701467',
#   'HUDA__UNIV_ID__c': 'JaZahn',
#   'HUDA__UPDATE_DT__c': '2018-10-23T02:32:49',
#   'HUDA__UPDATE_SOURCE__c': None,
#   'Id': 'aDmD40000001DrJKAU',
#   'HUDA__Name_Contact__c': '00336000010CxNQAA0'
# }])

# response = hsf.sf.Contact.metadata()
# response = hsf.getTypeMap(objects=testconfig.keys())
# logger.info(json.dumps(response))
# logger.info(pformat(json.dumps(response)))

# contact_results = hsf.getContactIds(id_type='HUDA__hud_UNIV_ID__c', ids=['91156571'])
# logger.info(pformat(contact_results))


