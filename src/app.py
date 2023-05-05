from common import isTaskRunning, logger, stack
import pds
from salesforce import HarvardSalesforce
from transformer import SalesforceTransformer
from departments import Departments

import os
import json
if stack == 'developer':
    from dotenv import load_dotenv
    load_dotenv() 


#### DEV debugging section #########
from pprint import pprint, pp, pformat

f = open('../example_config.json')
config = json.load(f)
f.close()

f = open('../example_pds_query.json')
pds_query = json.load(f)
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

        # TODO: GET data/watermark from dynamodb based on client

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
        hsf.getTypeMap(config.keys())

        # validate the config
        hsf.validateConfig(config)

        # TODO: implement updates_only
        updates_only = os.getenv('UPDATES_ONLY') or False

        # TODO: GET list of updated people since watermark 

        # query = {
        #     "conditions": {
        #         "univid": ["80719647"]
        #     }
        # }
        # this is a list of DotMaps, which was supposed to allow us to access the keys with dot notation
        people = pds.People(query=pds_query, apikey=os.getenv("PDS_APIKEY")).people

        # here we get the full list of departments
        departments = Departments(apikey=os.getenv("DEPT_APIKEY"))
        hashed_departments = departments.departments
        logger.debug(f"Successfully got {len(departments.results)} departments")

        transformer = SalesforceTransformer(config=config, hsf=hsf)

        # data will have the structure of { "OBJECT": [{"FIELD": "VALUE"}, ...]}
        # data = {}
        # data = transformer.transform(source_data=departments.results, source_name='departments')

        # logger.info(f"**** Push Departments to SF  ****")
        # for object, object_data in data.items():
        #     logger.debug(f"object: {object}")
        #     logger.debug(pformat(object_data))

            # hsf.pushBulk(object, object_data)    

        data = {}
        data = transformer.transform(source_data=people, source_name='pds')

        logger.info(f"**** Push People to SF  ****")
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

# #N/A doesn't seem to work for date/datetimes
# data = [{'HUDA__hud_ACADEMIC_PRIME_ROLE_INDICATOR__c': 'F',
#   'HUDA__hud_DEPT_ID__c': '104130',
#   'HUDA__hud_EFFDT__c': '2022-11-05T02:33:11',
#   'HUDA__hud_EFF_STATUS__c': 'A',
#   'HUDA__hud_POI_COMMENTS__c': None,
#   'HUDA__hud_EMP_ADDR_PS_LOCATION_CD__c': 'H86079',
#   'HUDA__hud_EMP_APPOINT_END_DT__c': '2023-09-30T00:00:00',
#   'HUDA__hud_EMP_DEPT_ENTRY_DT__c': '2022-11-01T00:00:00',
#   'HUDA__hud_EMP_EMPLOYMENT_STATUS__c': 'A',
#   'HUDA__hud_EMP_EMPL_CLASS__c': 'Y',
#   'HUDA__hud_EMP_FACULTY_CD__c': 'FAS',
#   'HUDA__hud_EMP_FULLTIME_FLAG__c': 'T',
#   'HUDA__hud_EMP_HIRE_DT__c': '2022-11-01T00:00:00',
#   'HUDA__hud_EMP_JOBCODE__c': '069591',
#   'HUDA__hud_EMP_MAJ_AFFILIATION_CD__c': 'FAS^MA',
#   'HUDA__hud_EMP_MAJ_AFFILIATION_DESC__c': 'Fac Arts & Scis Major Affil',
#   'HUDA__hud_EMP_PAID_FLAG__c': 'T',
#   'HUDA__hud_EMP_PAYGROUP__c': 'MIP',
#   'HUDA__hud_EMP_REHIRE_DT__c': '2022-11-01T00:00:00',
#   'HUDA__hud_EMP_SUB_AFFILIATION_CD__c': 'FAS_SCI^SA',
#   'HUDA__hud_EMP_SUB_AFFILIATION_DESC__c': 'FAS^Sciences',
#   'HUDA__hud_EMP_TERMINATION_DT__c': None,
#   'HUDA__hud_EMP_UNION_CD__c': '00',
#   'HUDA__hud_PERSON_ROLES_KEY__c': '6002319',
#   'HUDA__hud_PRIME_ROLE_INDICATOR__c': 'T',
#   'HUDA__hud_PRIVACY_VALUE__c': '5',
#   'HUDA__hud_ROLE_END_DT__c': None,
#   'HUDA__hud_ROLE_ID__c': '0',
#   'HUDA__hud_ROLE_SOURCE__c': 'PS',
#   'HUDA__hud_ROLE_START_DT__c': '2022-11-01T00:00:00',
#   'HUDA__hud_ROLE_TITLE__c': 'Post-Doctoral Fellow in FAS Informatics',
#   'HUDA__hud_ROLE_TYPE_CD__c': 'EMPLOYEE',
#   'HUDA__hud_SUPERVISOR_ID__c': '60751145',
#   'HUDA__hud_UPDATE_DT__c': '2022-11-05T02:33:11',
#   'Id': 'a0B1R000014NwyXUAS',
#   'hed__Contact__c': '0031R00002rj19OQAQ'}]
# otherdata = [
#  {'HUDA__hud_EFFDT__c': '2022-10-28T16:43:58',
#   'HUDA__hud_EFF_STATUS__c': 'A',
#   'HUDA__hud_PERSON_ROLES_KEY__c': '5998552',
#   'HUDA__hud_POI_COMMENTS__c': '#N/A',
#   'HUDA__hud_POI_COMPANY__c': '#N/A',
#   'HUDA__hud_POI_FACULTY_CD__c': 'FAS',
#   'HUDA__hud_POI_SHORT_DESC_LINE1__c': '#N/A',
#   'HUDA__hud_POI_SHORT_DESC_LINE2__c': '#N/A',
#   'HUDA__hud_PRIME_ROLE_INDICATOR__c': 'F',
#   'HUDA__hud_PRIVACY_VALUE__c': '1',
#   'HUDA__hud_ROLE_END_DT__c': '2022-11-08',
#   'HUDA__hud_ROLE_ID__c': '1',
#   'HUDA__hud_ROLE_SOURCE__c': 'PORTAL',
#   'HUDA__hud_ROLE_START_DT__c': '2022-11-01T00:00:00',
#   'HUDA__hud_ROLE_TITLE__c': 'Postdoctoral Fellow',
#   'HUDA__hud_ROLE_TYPE_CD__c': 'INCEMPL',
#   'HUDA__hud_UPDATE_DT__c': '2022-10-28T16:43:58',
#   'Id': 'a0B1R000014NwYLUA0',
#   'hed__Contact__c': '0031R00002rj19OQAQ'}]


# hsf.pushBulk("hed__Affiliation__c", data)


# response = hsf.sf.Contact.metadata()
# response = hsf.getTypeMap(objects=config.keys())
# logger.info(json.dumps(response))
# logger.info(pformat(json.dumps(response)))

# contact_results = hsf.getContactIds(id_type='HUDA__hud_UNIV_ID__c', ids=['91156571'])
# logger.info(pformat(contact_results))

# departments = Departments(apikey=os.getenv("DEPT_APIKEY")).departments
# logger.info(departments)