from common import logger

class SalesforceTransformer:
    def __init__(self, config, hsf):
        self.config = config
        self.hsf = hsf
        self.hashed_ids = {}

    def transform(self, people):

        logger.debug("Starting transfom")
        self.hashed_ids = self.hsf.getUniqueIds(config=self.config, people=people)

        data = {}
        for person in people:

            # go through all the objects
            for object_name in self.config:
                # current_record is an array because on records that aren't flat, 
                #   we're going to have to deal with multiples per person
                current_record = {}
                current_records = []

                # if it's flat, that means there's only one per person
                #   (otherwise, it's intention is to get a branch with multiple values per person,
                #   like names, emails, etc etc)
                is_flat = self.config[object_name].get('flat') or False    

                good_records = []
                best_branches = []
                good_branch = {}
                
                object_config = self.config[object_name]['fields']
                pds_id_name = self.config[object_name]['Id']['pds']
                salesforce_id_name = self.config[object_name]['Id']['salesforce']
                value_reference = ""
                logger.debug(f"object: {object_name}")

                # go through all of the target fields we'll be mapping to
                # target is the field name of the data item in Salesforce
                for target in object_config:
                    if not object_config[target]:
                        continue
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
                    elif isinstance(source_object, (str)):
                        value_reference = source_object
                    logger.debug(f"    value_reference: {value_reference}:{person[value_reference]}") # this will bork on branched values
                    logger.debug(f"    when: {when}")
                    
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

                            # if this branch passed the when (the tests)
                            if is_best:

                                # if we already have a qualifying branch, check the updateDate and change it if the updateDate is better
                                if best_branch is not None and is_flat and not when:
                                    if branch.updateDate > best_branch.updateDate:
                                        best_branch = branch
                                else: 
                                    best_branch = branch

                            if not is_flat:
                                id_name = self.hashed_ids[object_name]['id_name']
                                if "." in id_name:
                                    id_name.split(".")[1:]
                                if best_branch[id_name] not in [b[id_name] for b in best_branches]:
                                    best_branches.append(best_branch)

                                best_branches.append(best_branch)
                            

                        if best_branch is not None:
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

                    if is_flat:
                        if object_name not in current_record:
                            current_record[object_name] = {}
                        current_record = self.setId(person=person, object_name=object_name, current_record=current_record)
                        current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)
                    # else: 
                    #     current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)



                for branch in best_branches:
                    current_record = {}
                    branch_field_pieces = branch_field.split(".")
                    if len(branch_field_pieces) == 1:
                        value = branch[branch_field]
                    elif len(branch_field_pieces) == 2:
                        value = branch[branch_field_pieces[0]][branch_field_pieces[1]]
                    if object_name not in current_record:
                        current_record[object_name] = {}
                    for target in self.config[object_name]['fields']:
                        # source = self.config[object_name]['fields'][target]
                        # value = branch[source.split(".")[1:]]
                        # current_record[object_name][target] = self.hsf.validate(object=object_name, field=target, value=value)
                        pass
                    current_record = self.setId(person=person, object_name=object_name, current_record=current_record)
                    good_records.append(current_record[object_name])
                    

                if object_name not in data: 
                    data[object_name] = []

                if is_flat:
                    data[object_name] = []
                    data[object_name].append(current_record[object_name])
                else:
                    data[object_name] = good_records
            
        logger.debug("Transform finished")

        return data
    

    # this method will set the id of the current record given the person record, the object name and the config
    # NOTE: a record should be a single salesforce object name with objects that are not necessarily affiliated 
    #   with the same person
    def setId(self, person, object_name, current_record={}):
        
        if 'Id' in self.config[object_name]:
            source_object = self.config[object_name]['Id']
            if 'pds' in source_object and 'salesforce' in source_object:
                logger.debug(f"hashed: {self.hashed_ids[object_name]}")
                # then this is an Id we need to try and match
                id_name = self.hashed_ids[object_name]['id_name']
                salesforce_id_name = source_object['salesforce']
                current_id = None
                if '.' in id_name:
                    (branch_name, id_name) = id_name.split(".")
                    # we need to loop through all of the branches for this
                    for branch in person[branch_name]:
                        current_id = str(branch[id_name])
                        if current_id in self.hashed_ids[object_name]['Ids']:
                            value = self.hashed_ids[object_name]['Ids'][current_id]
                            if object_name not in current_record:
                                current_record[object_name] = {}
                            current_record[object_name][salesforce_id_name] = self.hsf.validate(object=object_name, field=salesforce_id_name, value=value)

                else:
                    current_id = person[id_name]

                    if current_id in self.hashed_ids[object_name]['Ids']:
                        value = self.hashed_ids[object_name]['Ids'][current_id]

                    if object_name not in current_record:
                        current_record[object_name] = {}
                    current_record[object_name][salesforce_id_name] = self.hsf.validate(object=object_name, field=salesforce_id_name, value=value)
            else:
                raise Exception("Error: config object's Id requires a pds and salesforce value to be able to match")
                
        return current_record
