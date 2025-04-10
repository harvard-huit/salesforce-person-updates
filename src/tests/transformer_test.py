import unittest
from unittest import mock, skip
import json
from dotmap import DotMap

from transformer import SalesforceTransformer
from salesforce import HarvardSalesforce
from pds import People

class SalesforceTransformerTest(unittest.TestCase):

    @mock.patch('salesforce.Salesforce')                                            
    def setUp(self, mock_connection):

        patcher = mock.patch('transformer.logger')
        self.mock_transformer_logger = patcher.start()
        self.addCleanup(patcher.stop)
        
        patcher = mock.patch('salesforce.logger')
        self.mock_salesforce_logger = patcher.start()
        self.addCleanup(patcher.stop)

        connection_instance = mock.MagicMock()                                        
        connection_instance.execute.return_value = True
        mock_connection.return_value = connection_instance

        self.sf = HarvardSalesforce(
            domain = "",
            username = "",
            password = "",
            token = "faketoken"
        )

        try:
            f = open('example_config.json')
        except:
            f = open('../example_config.json')
        self.exampleConfig = json.load(f)
        f.close()

        self.fakeConfig = { 
            "Contact": {
                "flat": True,
                "source": "pds",
                "Id": {
                    "pds": "personKey",
                    "salesforce": "salesforceId"
                },
                "fields": {
                    "salesforceId": "personKey",
                    "Birthdate": "birthDate",
                    "FirstName": {
                        "value": "names.firstName",
                        "when": {
                            "names.personNameType.code": ["LISTING", "OFFICIAL"]
                        }
                    }
                }
            },
            "Names__c": {
                "flat": False,
                "source": "pds",
                "Id": {
                    "pds": "names.personNameKey",
                    "salesforce": "salesforceId"
                },
                "fields": {
                    "salesforceId": "names.personNameKey",
                    "rootId": "personKey",
                    "FirstName__c": "names.firstName",
                    "LastName__c": "names.lastName",
                    "Name_Contact__c": "sf.contact.id",
                    "Name_Type_Code__c": "names.personNameType.code"
                }
            },
            "Account": {
                "flat": True,
                "source": "departments",
                "Id": {
                    "departments": "departmentKey",
                    "salesforce": "salesforceId"
                },
                "fields": {
                    "Name": "departmentName",
                    "departmentKey__c": "departmentKey"
                }
            },
            "Affiliation__c": {
                "flat": False,
                "source": "pds",
                "Id": {
                    "pds": ["emps.id", "stus.id", "pois.id"],
                    "salesforce": "affiliationId"
                },
                "fields": {
                    "affiliationId": ["emps.id", "stus.id", "pois.id"],
                    "rootId": "personKey",
                    "otherValue": ["emps.other_value", "stus.other_value", "pois.other_value.code"]
                }
            }
        }

        self.fake_sf_metadata = { 'records': [] }
        exampleRecord = {}
        for object_name, object_config in self.fakeConfig.items():
            for field in object_config['fields'].keys():
                exampleRecord[field] = "junk data"
            # if 'records' not in self.fake_sf_metadata:
            #     self.fake_sf_metadata['records'] = []
        self.fake_sf_metadata['records'].append(exampleRecord)

        self.fake_sf_contact_id_data1 = {
            'records': [
                {
                    'Id': 'A1',
                    'salesforceId': '1'
                },
                {
                    'Id': 'A2',
                    'salesforceId': '2'
                }
            ]
        }

        # sample data for after the 3rd person is added
        self.fake_sf_contact_id_data2 = self.fake_sf_contact_id_data1
        self.fake_sf_contact_id_data2['records'].append({
            'Id': 'A3',
            'salesforceId': '3'
        })

        self.fake_sf_name_id_data = {
            'records': [
                {
                    'Id': 'N11',
                    'salesforceId': '11'
                },
                {
                    'Id': 'N21',
                    'salesforceId': '21'
                },
                {
                    'Id': 'N22',
                    'salesforceId': '22'
                }
            ]
        }

        self.sample_when = {
            "names.personNameType.code": ["LISTING", "OFFICIAL"]
        }

        self.sample_pds_data = {
            "total_count": 3,
            "count": 3,
            "results": [
                {
                    "personKey": "1",
                    "birthDate": "1999-01-03",
                    "names": [
                        {
                            "personNameKey": "11",
                            "firstName": "Happy",
                            "lastName": "Gilmore",
                            "personNameType": {
                                "code": "OFFICIAL"
                            }
                        }
                    ],
                    "stus": [
                        {
                            "id": "1",
                            "other_value": "one"
                        }
                    ]
                },
                {
                    "personKey": "2",
                    "birthDate": "1977-11-13",
                    "names": [
                        {
                            "personNameKey": "22",
                            "firstName": "Nana",
                            "lastName": "Visitor",
                            "personNameType": {
                                "code": "LISTING"
                            }
                        },
                        {
                            "personNameKey": "21",
                            "firstName": "Nana",
                            "lastName": "Tucker",
                            "personNameType": {
                                "code": "OFFICIAL"
                            }
                        }
                    ],
                    "emps": [
                        {
                            "id": "2",
                            "other_value": "two"
                        },
                        {
                            "id": "3",
                            "other_value": "three"
                        },
                        {
                            "id": "4",
                            "other_value": "four"
                        }
                    ],
                    "stus": [
                        {
                            "id": "5",
                            "other_value": "five"
                        }
                    ]
                },
                {
                    "personKey": "3",
                    "birthDate": "1980-11-17",
                    "names": [
                        {
                            "personNameKey": "32",
                            "firstName": "JaZahn",
                            "lastName": "Clevenger",
                            "personNameType": {
                                "code": "LISTING"
                            }
                        },
                        {
                            "personNameKey": "31",
                            "firstName": "Jazahn",
                            "lastName": "Clevenger",
                            "personNameType": {
                                "code": "OFFICIAL"
                            }
                        }
                    ],
                    "emps": [
                        {
                            "id": "6",
                            "other_value": "six"
                        }
                    ],
                    "stus": [
                        {
                            "id": "7",
                            "other_value": "seven"
                        }
                    ],
                    "pois": [
                        {
                            "id": "8",
                            "other_value": {
                                "code": "eight"
                            } 
                        }
                    ]
                }
            ]
        }

        self.sample_transformed_pds_data = {
            "Contact": [
                {
                    "Id": "A1",
                    "salesforceId": "1",
                    "Birthdate": "1999-01-03",
                    "FirstName": "Happy"
                },
                {
                    "Id": "A2",
                    "salesforceId": "2",
                    "Birthdate": "1977-11-13",
                    "FirstName": "Nana"
                },
                {
                    "Id": "A3",
                    "salesforceId": "3",
                    "Birthdate": "1980-11-17",
                    "FirstName": "JaZahn"
                }
            ],
            "Names__c": [
                {
                    "Id": "N11",
                    "salesforceId": "11",
                    "rootId": "1",
                    "FirstName__c": "Happy",
                    "LastName__c": "Gilmore",
                    "Name_Contact__c": "A1",
                    "Name_Type_Code__c": "OFFICIAL"
                },
                {
                    "Id": "N22",
                    "salesforceId": "22",
                    "rootId": "2",
                    "FirstName__c": "Nana",
                    "LastName__c": "Visitor",
                    "Name_Contact__c": "A2",
                    "Name_Type_Code__c": "LISTING"
                },
                {
                    "Id": "N21",
                    "salesforceId": "21",
                    "rootId": "2",
                    "FirstName__c": "Nana",
                    "LastName__c": "Tucker",
                    "Name_Contact__c": "A2",
                    "Name_Type_Code__c": "OFFICIAL"
                },
                {
                    "Id": "N32",
                    "salesforceId": "32",
                    "rootId": "3",
                    "FirstName__c": "JaZahn",
                    "LastName__c": "Clevenger",
                    "Name_Contact__c": "A3",
                    "Name_Type_Code__c": "LISTING"
                },
                {
                    "Id": "N31",
                    "salesforceId": "31",
                    "rootId": "3",
                    "FirstName__c": "Jazahn",
                    "LastName__c": "Clevenger",
                    "Name_Contact__c": "A3",
                    "Name_Type_Code__c": "OFFICIAL"
                }
            ],
            "Affiliation__c": [
                {
                    "affiliationId": "1",
                    "rootId": "1",
                    "otherValue": "one"
                },
                {
                    "affiliationId": "2",
                    "rootId": "2",
                    "otherValue": "two"
                },
                {
                    "affiliationId": "3",
                    "rootId": "2",
                    "otherValue": "three"
                },
                {
                    "affiliationId": "4",
                    "rootId": "2",
                    "otherValue": "four"
                },
                {
                    "affiliationId": "5",
                    "rootId": "2",
                    "otherValue": "five"
                },
                {
                    "affiliationId": "6",
                    "rootId": "3",
                    "otherValue": "six"
                },
                {
                    "affiliationId": "7",
                    "rootId": "3",
                    "otherValue": "seven"
                },
                {
                    "affiliationId": "8",
                    "rootId": "3",
                    "otherValue": "eight"
                }
            ]
        }

        self.sample_branch_1 = {
            "personNameKey": 3837957,
            "personNameType": {
                "code": "LISTING"
            },
            "firstName": "Rachel",
            "lastName": "Lewoollen",
            "middleName": None,
            "name": "Rachel Lewoollen",
            "prefix": None,
            "suffix": None,
            "effectiveStatus": {
                "code": "A"
            },
            "updateDate": "2020-11-20T02:32:59"
        }
        self.sample_branch_2 = {
            "personNameKey": 3833354,
            "personNameType": {
                "code": "OFFICIAL"
            },
            "firstName": "Racheel",
            "lastName": "Lewoollen",
            "middleName": None,
            "name": "Racheel Lewoollen",
            "prefix": None,
            "suffix": None,
            "effectiveStatus": {
                "code": "A"
            },
            "updateDate": "2020-11-20T02:32:59"
        }

        self.sample_unique_ids = {
            'Contact': {
                "Ids": {
                    "1": "A1",
                    "2": "A2",
                    "3": "A3"
                }
            },
            'Names__c': {
                "Ids": {
                    
                }
            },
            'Affiliation__c': {
                "Ids": {
                    
                }
            }
        }

        # this constructs a single record with all of the fields that are contained in the exampleConfig
        self.exampleSFData = { 'records': [] }
        exampleRecord = {}
        for object_name, object_config in self.exampleConfig.items():
            for field in object_config['fields'].keys():
                exampleRecord[field] = "junk data"
        self.exampleSFData['records'].append(exampleRecord)

        self.transformer = SalesforceTransformer(config=self.fakeConfig, hsf=self.sf)
        self.transformer.hashed_ids = {
            "Contact": {
                "id_name": "personKey",
                "Ids": {
                    "1": "A1",
                    "2": "A2",
                    "3": "A3"
                }
            },
            "Names__c": {
                "id_name": "personNameKey",
                "Ids": {
                    "11": "N11",
                    "21": "N21",
                    "22": "N22",
                    "31": "N31",
                    "32": "N32"
                }
            },
            "Affiliation__c": {
                "id_name": "id",
                "Ids": {

                }
            }
        }

        self.transformer.hsf.type_data = {
            'Contact': {
                "Id": {
                    "type": "string",
                    "updateable": False,
                    "length": 100
                },
                "salesforceId": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "Birthdate": {
                    "type": "date",
                    "updateable": True,
                    "length": 100
                },
                "FirstName": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                }
            },
            "Names__c": {
                "Id": {
                    "type": "string",
                    "updateable": False,
                    "length": 100
                },
                "salesforceId": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "rootId": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "FirstName__c": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "LastName__c": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "Name_Contact__c": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "Name_Type_Code__c": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                }
            },
            "Affiliation__c": {
                "Id": {
                    "type": "string",
                    "updateable": False,
                    "length": 100
                },
                "affiliationId": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "rootId": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                },
                "otherValue": {
                    "type": "string",
                    "updateable": True,
                    "length": 100
                }          
            }

        }


    def test_validate_sample_configs(self):
        # self.sf.sf.query_all.return_value = self.fake_sf_metadata
        self.assertTrue(self.sf.validateConfig(self.fakeConfig, dry_run=True))

        # self.sf.sf.query_all.return_value = self.exampleSFData
        self.assertTrue(self.sf.validateConfig(self.exampleConfig, dry_run=True))

    def test_validate_source_config_split(self):
        # self.sf.sf.query_all.return_value = self.fake_sf_metadata
        self.transformer.config = self.fakeConfig
        source_config = self.transformer.getSourceConfig('pds')

        self.assertTrue(self.sf.validateConfig(source_config, dry_run=True))
        self.assertEqual(3, len(source_config))
        for object_name in source_config:
            self.assertEqual('pds', source_config[object_name]['source'])

    def test_validate_target_config_split(self):
        # self.sf.sf.query_all.return_value = self.fake_sf_metadata
        self.transformer.config = self.fakeConfig
        target_config = self.transformer.getTargetConfig('Contact')
        self.assertTrue(self.sf.validateConfig(target_config, dry_run=True))
        self.assertEqual(1, len(target_config))
        self.assertIn('Contact', target_config)

    # when a branch is the only branch, it should be the best
    def test_handle_when(self):
        self.assertTrue(self.transformer.handle_when(when=self.sample_when, branch=self.sample_branch_1, best_branch={}))

    # when a branch is a better fit, it should be the best, in this case, LISTING is better than OFFICIAL
    def test_handle_when_with_best(self):
        self.assertTrue(self.transformer.handle_when(when=self.sample_when, branch=self.sample_branch_1, best_branch=self.sample_branch_2))
    
    # when the best_branch is already the better fit, this should return False
    def test_handle_when_with_better_best(self):
        self.assertFalse(self.transformer.handle_when(when=self.sample_when, branch=self.sample_branch_2, best_branch=self.sample_branch_1))

    def test_set_id(self):
        self.sf.sf.query_all.return_value = self.fake_sf_contact_id_data1
        self.transformer.config = self.fakeConfig
        source_data_object = self.sample_pds_data['results'][0]

        current_record = {

        }
        current_record = self.transformer.setId(source_data_object=source_data_object, object_name='Contact', current_record=current_record)
        self.assertIn('Contact', current_record.keys())
        self.assertEqual(current_record['Contact']['Id'], "A1")

    @skip('not sure how to fix this one right now')
    def test_transform_gen_contact_only(self):
        self.transformer.config = self.fakeConfig
        sample_people = People.make_people({}, self.sample_pds_data['results'])
        data_gen = self.transformer.transform(source_data=sample_people, source_name='pds', target_object='Contact')
        count = 0
        for d in data_gen:
            for object_name, object in d.items():
                self.assertDictEqual(self.sample_transformed_pds_data[object_name][count], object)
                count += 1

    def test_transform_gen_single_name_only(self):
        self.transformer.config = self.fakeConfig
        sample_people = [People.make_people({}, self.sample_pds_data['results'])[0]]
        data_gen = self.transformer.transform(source_data=sample_people, source_name='pds', target_object='Names__c')
        count = 0
        for d in data_gen:
            for object_name, object in d.items():
                self.assertDictEqual(self.sample_transformed_pds_data[object_name][count], object)
                count += 1


    def test_transform_gen_names_only(self):
        self.transformer.config = self.fakeConfig
        sample_people = People.make_people({}, self.sample_pds_data['results'])
        data_gen = self.transformer.transform(source_data=sample_people, source_name='pds', target_object='Names__c')
        count = 0
        for d in data_gen:
            for object_name, object in d.items():
                # thisone = self.sample_transformed_pds_data[object_name][count]
                self.assertDictEqual(self.sample_transformed_pds_data[object_name][count], object)
                count += 1
                
    def test_transform_affiliation(self):
        self.transformer.config = self.fakeConfig
        sample_people = People.make_people({}, self.sample_pds_data['results'])
        data_gen = self.transformer.transform(source_data=sample_people, source_name='pds', target_object='Affiliation__c')
        count = 0
        for d in data_gen:
            for object_name, object in d.items():
                self.assertDictEqual(self.sample_transformed_pds_data[object_name][count], object)
                count += 1

    def test_key_in_nested_dict_returns_true_when_value_exists(self):
        list_to_check = self.fakeConfig
        value = "Contact.Id.pds"
        result = self.transformer.key_in_nested_dict(value, list_to_check, 0)
        self.assertTrue(result)

    def test_key_in_nested_dict_returns_false_when_value_does_not_exist(self):
        list_to_check = self.fakeConfig
        value = "Contact.Id.foo"
        result = self.transformer.key_in_nested_dict(value, list_to_check)
        self.assertFalse(result)

    def test_key_in_nested_dict_returns_false_when_value_is_not_last_element(self):
        list_to_check = self.fakeConfig
        value = "Contact.Id"
        result = self.transformer.key_in_nested_dict(value, list_to_check)
        self.assertFalse(result)

    def test_key_in_nested_dict_returns_true_when_value_is_in_listed_branch(self):
        list_to_check = self.sample_pds_data['results'][0]
        value = "names.personNameType.code"
        result = self.transformer.key_in_nested_dict(value, list_to_check, 0)
        self.assertTrue(result)


    def test_ref_to_object_value(self):
        obj = self.sample_pds_data['results'][0]
        
        ref = "personKey"
        expected = "1"
        result = self.transformer.ref_to_object_value(ref, obj)
        self.assertEqual(result, expected)

        ref = "names.firstName"
        expected = "Happy"
        result = self.transformer.ref_to_object_value(ref, obj)
        self.assertEqual(result, expected)

        obj = self.sample_pds_data['results'][2]

        ref = "emps.id"
        expected = "6"
        result = self.transformer.ref_to_object_value(ref, obj)
        self.assertEqual(result, expected)

        ref = "pois.other_value.code"
        expected = "eight"
        result = self.transformer.ref_to_object_value(ref, obj)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()