from common import isTaskRunning, logger, stack
import pds
from salesforce import HarvardSalesforce

import os
import json
from dotenv import load_dotenv
load_dotenv() 


#### DEV debugging section
from pprint import pprint, pp, pformat

f = open('../example_config.json')
testconfig = json.load(f)
f.close()

f = open('../example_pds_query.json')
testquery = json.load(f)
f.close()

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


        ids = []
        hashed_results = {}
        for person in people:
            ids.append(person.univid)
            hashed_results[person.univid] = person
        

        # GET list of people from salesforce that match the ids we got back from the pds call
        # contact_results = hsf.getContactIds(id_type='HUDA__hud_UNIV_ID__c', ids=ids)
        # hashed_contacts = {}
        # for contact in contact_results['records']:
        #     hashed_contacts[contact['HUDA__hud_UNIV_ID__c']] = contact['Id']
        
        # get a map of ids for matching
        hashed_ids = hsf.getUniqueIds(config=testconfig, people=people)


        # data will have the structure of { "OBJECT": [{"FIELD": "VALUE"}, ...]}
        data = {}
        for person in people:

            current_record = testconfig
            # go through all the objects
            for object_name in testconfig:
                object_config = testconfig[object_name]
                value_reference = ""
                logger.debug(f"object: {object_name}")

                # go through all of the target fields we'll be mapping to
                for target in object_config:
                    source_object = object_config[target]
                    logger.debug(f"  target: {target}")
                    # value that we're sending to SF
                    value = ""

                    when = None
                    logger.debug(f"  source_object: {source_object}")
                    if isinstance(source_object, (dict)):
                        if 'value' in source_object:
                            value_reference = source_object['value']
                        if 'when' in source_object:
                            when = source_object['when']
                        if 'pds' in source_object and 'salesforce' in source_object:
                            # then this is an Id we need to try and match
                            id_name = hashed_ids[object_name]['id_name']
                            current_id = person[id_name]
                            value = hashed_ids[object_name]['Ids'][current_id]
                            current_record[object_name][target] = hsf.validate(object=object_name, field=target, value=value)
                            continue
                    elif isinstance(source_object, (str)):
                        value_reference = source_object
                    # logger.debug(f"    value_reference: {value_reference}:{person[value_reference]}") # this will bork on branched values

                    # logger.debug(f"when: {when}")
                    
                    pieces = value_reference.split(".")
                    first = pieces[0]
                    
                    # check the value referenced in the config
                    if isinstance(person[first], (str, bool)):
                        value = person[first]
                    elif isinstance(person[first], dict):
                        # if it's a dict, we need to get the piece further in
                        if isinstance(person[first][pieces[1]], dict):
                            value = person[first][pieces[1]][pieces[2]]
                        else:
                            value = person[first][pieces[1]]
                    elif isinstance(person[first], list):
                        branches = person[first]
                        # ignore the first piece of the dotted element
                        branch_field = ".".join(pieces[1:])

                        # initialize the best branch as None
                        best_branch = None

                        # now that we know we're on a branch, we need to loop through the possible values
                        for branch in branches:

                            kill_best = False
                            is_best = True
                            # if there is a when clause, figure out if this branch matches
                            if isinstance(when, dict):
                                for ref, val in when.items():

                                    if ref.split(".")[0] not in branch:
                                        ref = ".".join(ref.split(".")[1:])
                                    # if this pds reference is not in the branch, try it without the first element,
                                    #   this allows for `names.name` and `name` to work
                                    # if it's still not there, that's a problem, maybe I should just ignore this?
                                    if ref.split(".")[0] not in branch:
                                        raise Exception(f"Error: invalid reference in when: trying to find {ref} in {branch}")

                                    # if the when value is a list, we want to get the "best", this is annoying
                                    if isinstance(val, list):
                                        is_best = False
                                        for v in val:
                                            # if the best branch already has this value, don't bother with the loop
                                            #   this means the current branch isn't better
                                            ref_pieces = ref.split(".")

                                            if len(ref_pieces) == 1:
                                                if best_branch is not None:
                                                    if best_branch[ref] == v and branch[ref] != v:
                                                        break

                                                if branch[ref] == v:
                                                    is_best = True
                                                    kill_best = True
                                                    break
                                            elif len(ref_pieces) == 2:
                                                if best_branch is not None:
                                                    if best_branch[ref_pieces[0]][ref_pieces[1]] == v and branch[ref_pieces[0]][ref_pieces[1]] != v:
                                                        break

                                                if branch[ref_pieces[0]][ref_pieces[1]] == v:
                                                    is_best = True
                                                    kill_best = True
                                                    break
                                            else: 
                                                raise Exception(f"Error: Reference not recognized: {ref}")

                                        
                                                                                        
                                    elif isinstance(val, (str, bool, int)):

                                        ref_pieces = ref.split(".")

                                        if len(ref_pieces) == 1:
                                            if branch[ref] != val:
                                                is_best = False
                                                break
                                        elif len(ref_pieces) == 2:
                                            if branch[ref_pieces[0]][ref_pieces[1]] != val:
                                                is_best = False
                                                break
                                        else: 
                                            raise Exception(f"Error: Reference not recognized: {ref}")

                            # if this branch passed the when
                            if is_best:                          
                                if kill_best:
                                    best_branch = None

                                # if we already have a qualifying branch, check the updateDate and change it if the updateDate is better
                                if best_branch is not None:
                                    if branch.updateDate > best_branch.updateDate:
                                        best_branch = branch
                                else: 
                                    best_branch = branch
                        

                        if best_branch is not None:
                            branch_field_pieces = branch_field.split(".")
                            if len(branch_field_pieces) == 1:
                                value = best_branch[branch_field]
                            elif len(branch_field_pieces) == 2:
                                value = best_branch[branch_field_pieces[0]][branch_field_pieces[1]]
                        else:
                            value = None


                    logger.debug(f"      value: {value}")

                    current_record[object_name][target] = hsf.validate(object=object_name, field=target, value=value)
                     
            if object_name not in data:
                data[object_name] = []
            data[object_name].append(current_record[object_name])



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


# response = hsf.sf.Contact.metadata()
# response = hsf.getTypeMap(objects=testconfig.keys())
# logger.info(json.dumps(response))
# logger.info(pformat(json.dumps(response)))