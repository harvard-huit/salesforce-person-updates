from common import logger
import re
from pprint import pprint, pp, pformat


class SalesforceTransformer:
    def __init__(self, config, hsf):
        self.config = config
        self.hsf = hsf
        self.hashed_ids = {}

    # This method helps sort out the config to get a subsection of the config for a specific source
    def getSourceConfig(self, source: str) -> dict: 
        split_config = {}
        for object_name in self.config:
            if 'source' in self.config[object_name]:
                if self.config[object_name]['source'] == source:
                    split_config[object_name] = self.config[object_name]
        return split_config

    def getTargetConfig(self, target_object: str) -> dict:
        split_config = {}
        for object_name in self.config:
            if object_name == target_object:
                split_config[object_name] = self.config[object_name]

        return split_config

    def transform(self, source_data, source_name=None, target_object=None, exclude_target_objects=[]):

        logger.debug("Starting transfom")
        if target_object is not None:
            source_config = self.getTargetConfig(target_object)
            source_name = source_config[target_object]['source']
        elif source_name is not None:
            source_config = self.getSourceConfig(source_name)
        else:
            source_config = self.config
        self.hashed_ids = self.hsf.getUniqueIds(config=source_config, source_data=source_data)

        data = {}
        best_branches = {}
        for source_data_object in source_data:

            salesforce_person = {}
            if 'Contact' in self.hashed_ids:
                if self.hashed_ids['Contact']['id_name'] in source_data_object:
                    if source_data_object[self.hashed_ids['Contact']['id_name']] in self.hashed_ids['Contact']['Ids']:
                        salesforce_person = {
                            "contact": {
                                "id": self.hashed_ids['Contact']['Ids'][source_data_object[self.hashed_ids['Contact']['id_name']]]
                            }
                        }


            # go through all the objects
            for object_name in source_config:
                if object_name in exclude_target_objects:
                    continue
                current_record = {}
                if source_name is None:
                    source_name = source_config[object_name]['source']

                # if it's flat, that means there's only one per "person"
                #   (otherwise, it's intention is to get a branch with multiple values per "person",
                #   like names, emails, etc etc)
                is_flat = source_config[object_name].get('flat') or False    

                good_records = []
                
                object_config = source_config[object_name]['fields']
                source_id_name = source_config[object_name]['Id'][source_name]
                salesforce_id_name = source_config[object_name]['Id']['salesforce']

                logger.debug(f"object: {object_name}")

                # go through all of the target fields we'll be mapping to
                # target is the field name of the data item in Salesforce
                for target in object_config:
                    value_reference = ""

                    # if the source field is not defined, just skip this field
                    # we might have an empty field to remind us that we _can_ populate it
                    if not object_config[target]:
                        continue

                    logger.debug(f"  target: {target}")
                    source_object = object_config[target]

                    # value that we're sending to SF
                    value = ""

                    is_branched = False

                    when = None
                    logger.debug(f"  source_object: {source_object}")

                    
                    if isinstance(source_object, list): 
                        value_references = source_object
                    else: 
                        if isinstance(source_object, (dict)):
                            if 'value' in source_object:
                                value_references = [source_object['value']]
                            if 'when' in source_object:
                                when = source_object['when']
                        elif isinstance(source_object, (str)):
                            value_references = [source_object]

                    for value_reference in value_references:


                        pieces = value_reference.split(".")
                        first = pieces[0]

                        logger.debug(f"    value_reference: {value_reference}:{source_data_object.get(value_reference)}")                     
                        logger.debug(f"    when: {when}")
                        
                        
                        # check the value referenced in the config
                        if isinstance(source_data_object[first], (str, bool, int)):
                            value = source_data_object[first]
                        elif isinstance(source_data_object[first], dict):
                            # if it's a dict, we need to get the piece further in
                            if pieces[1] not in source_data_object[first]:
                                if first == 'sf':
                                    source_pieces = pieces[1:]
                                    if source_pieces[0] in salesforce_person:
                                        if isinstance(salesforce_person, (str, bool, int)):
                                            value = salesforce_person[source_pieces[0]]
                                        elif isinstance(salesforce_person, dict) and len(source_pieces) == 2:
                                            value = salesforce_person[source_pieces[0]][source_pieces[1]]
                                        if object_name not in current_record:
                                            current_record[object_name] = {}
                                        current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)
                                    else:
                                        # then this person is not currently in salesforce
                                        logger.warn(f"Warning: reference not found in Salesforce object ({first})")
                                else:
                                    pass
                                    # logger.warn(f"Warning: reference ({pieces[1]}) not found in object ({source_data_object[first]})")
                                # if it's not in this person, just skip it
                                continue
                            if isinstance(source_data_object[first][pieces[1]], dict):
                                value = source_data_object[first][pieces[1]][pieces[2]]
                            else:
                                value = source_data_object[first][pieces[1]]

                            # we are making an assumption here that if it's a sf value, it's required, 
                            #   (otherwise it'll end up orphaned)
                            if first == 'sf' and value in [None, '#N/A']:
                                raise Exception(f"Error: this value should not be null")
                            
                        elif isinstance(source_data_object[first], list):
                            is_branched = True
                            branches = source_data_object[first]
                            # ignore the first piece of the dotted element
                            branch_field = ".".join(pieces[1:])

                            # initialize the best branch as None
                            best_branch = None

                            # now that we know we're on a branch, we need to loop through the possible values
                            for branch in branches:

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
                                                    if best_branch:
                                                        if best_branch[ref] == v and branch[ref] != v:
                                                            break

                                                    if branch[ref] == v:
                                                        is_best = True
                                                        kill_best = True
                                                        break
                                                elif len(ref_pieces) == 2:
                                                    if best_branch:
                                                        if best_branch[ref_pieces[0]][ref_pieces[1]] == v and branch[ref_pieces[0]][ref_pieces[1]] != v:
                                                            break

                                                    if branch[ref_pieces[0]][ref_pieces[1]] == v:
                                                        is_best = True
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

                                # if this branch passed the when tests
                                if is_best:

                                    # if we already have a qualifying branch, check the updateDate and change it if the updateDate is better
                                    if best_branch and is_flat:
                                        if branch.updateDate > best_branch.updateDate:
                                            best_branch = branch
                                    else: 
                                        best_branch = branch

                                if not is_flat:
                                    source_id_name = self.hashed_ids[object_name]['id_name']
                                    if isinstance(source_id_name, list):
                                        for current_id_name in self.hashed_ids[object_name]['id_name']:
                                            # NOTE: I really don't like this, 
                                            #       but I can't think of a cleaner way to do it right now
                                            if re.search(rf"^{first}", current_id_name, re.IGNORECASE):
                                                source_id_name = current_id_name
                                                break
                                        # if it's still a list, that means we didn't get a match :(
                                        if isinstance(source_id_name, list):
                                            raise Exception(f"Error: branch {branch_name} not found in source id {source_id_name}")

                                    if "." in source_id_name:
                                        (branch_name, source_id_name) = source_id_name.split(".")
                                    pds_branch_id = str(best_branch[source_id_name])
                                    if pds_branch_id not in best_branches.keys():
                                        best_branches[pds_branch_id] = {}

                                    # need this for identifying the branch type later
                                    best_branch['branch_name'] = first

                                    best_branches[pds_branch_id] = best_branch

                                

                            if best_branch:
                                if is_flat:
                                    branch_field_pieces = branch_field.split(".")
                                    if len(branch_field_pieces) == 1:
                                        value = best_branch[branch_field]
                                    elif len(branch_field_pieces) == 2:
                                        value = best_branch[branch_field_pieces[0]][branch_field_pieces[1]]

                                    
                            else:
                                value = None
                        

                        if isinstance(value, bool):
                            if value:
                                value = 'Y'
                            else:
                                value = 'N'
                        logger.debug(f"      value: {value}")


                        if not is_branched:
                            if object_name not in current_record:
                                current_record[object_name] = {}
                            current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)
                        elif best_branch and is_flat: 
                            current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)

                    # END TARGET ***********************************************

                branch = {}
                for pds_branch_id, branch in best_branches.items():
                    
                    current_record[object_name] = {}
                    branch_name = branch['branch_name']
                    
                    # if this id is in the hashed_ids, that means it'll be an update and we need to add the Object Id
                    if pds_branch_id in self.hashed_ids[object_name]['Ids']:
                        sf_id = self.hashed_ids[object_name]['Ids'][pds_branch_id]
                        current_record[object_name]['Id'] = sf_id
                    for target, source_value in source_config[object_name]['fields'].items():
                        
                        if isinstance(source_value, list):
                            sources = source_value
                        else: 
                            sources = [source_value]
                        # source = source_value

                        for source in sources:
                            # for source in sources:
                            logger.debug(f"source: {source}")
                            value = None
                            source_pieces = source.split(".")
                            if source_pieces[0] not in [branch_name, 'sf']:
                                continue
                            branch_temp = branch
                            if source_pieces[0] in source_data_object:
                                logger.debug(f"  {source_pieces[0]} in source_data_object")
                                if isinstance(source_data_object[source_pieces[0]], list):
                                    source_pieces = source_pieces[1:]
                                else:
                                    branch_temp = source_data_object
                            if source_pieces[0] in branch_temp:
                                logger.debug(f"  {source_pieces[0]} in branch")
                                if len(source_pieces) == 1:
                                    value = branch_temp[source_pieces[0]]
                                elif len(source_pieces) == 2:
                                    if source_pieces[1] in branch_temp[source_pieces[0]]:
                                        value = branch_temp[source_pieces[0]][source_pieces[1]]
                                current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)
                            if source_pieces[0] == 'sf':
                                source_pieces = source_pieces[1:]
                                if source_pieces[0] in salesforce_person:
                                    if isinstance(salesforce_person, (str, bool, int)):
                                        value = salesforce_person[source_pieces[0]]
                                    elif isinstance(salesforce_person, dict) and len(source_pieces) == 2:
                                        value = salesforce_person[source_pieces[0]][source_pieces[1]]
                                    current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)

                        # logger.warn(f"Warning: unable to find valid source: ({source})")

                    good_records.append(current_record[object_name])
                    

                if object_name not in data: 
                    data[object_name] = []

                if is_flat:
                    current_record = self.setId(source_data_object=source_data_object, object_name=object_name, current_record=current_record)
                    data[object_name].append(current_record[object_name])
                elif not is_branched:
                    current_record = self.setId(source_data_object=source_data_object, object_name=object_name, current_record=current_record)
                    data[object_name].append(current_record[object_name])
                else:
                    data[object_name] = good_records
            
        logger.debug("Transform finished")

        return data
    

    # this method will set the id of the current record given the source_data_object record, the object name and the config
    # NOTE: a record should be a single salesforce object name with objects that are not necessarily affiliated 
    #   with the same source_data_object
    def setId(self, source_data_object, object_name, current_record={}):
        
        if 'Id' in self.config[object_name]:
            source_object = self.config[object_name]['Id']
            source_name = self.config[object_name]['source']
            if source_name in source_object and 'salesforce' in source_object:
                # logger.debug(f"hashed: {self.hashed_ids[object_name]}")
                # then this is an Id we need to try and match
                id_names = self.hashed_ids[object_name]['id_name']
                salesforce_id_name = source_object['salesforce']
                current_id = None
                value = None
                if not isinstance(id_names, list):
                    id_names = [id_names]
                for id_name in id_names:
                    if '.' in id_name:
                        (branch_name, id_name) = id_name.split(".")
                        # we need to loop through all of the branches for this
                        for branch in source_data_object[branch_name]:
                            if id_name not in branch:
                                continue
                            current_id = str(branch[id_name])
                            if current_id in self.hashed_ids[object_name]['Ids']:
                                value = self.hashed_ids[object_name]['Ids'][current_id]
                                if object_name not in current_record:
                                    current_record[object_name] = {}
                                current_record[object_name][salesforce_id_name] = self.hsf.validate(object=object_name, field=salesforce_id_name, value=value)

                    else:
                        current_id = source_data_object[id_name]

                        if current_id in self.hashed_ids[object_name]['Ids']:
                            value = self.hashed_ids[object_name]['Ids'][current_id]

                        if object_name not in current_record:
                            current_record[object_name] = {}
                        if value is not None:
                            current_record[object_name]['Id'] = self.hsf.validate(object=object_name, field='Id', value=value)
            else:
                raise Exception("Error: config object's Id requires a pds and salesforce value to be able to match")
        return current_record
                        
        

