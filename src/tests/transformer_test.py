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
                    "FirstName__c": "Happy",
                    "LastName__c": "Gilmore",
                    "Name_Contact__c": "A1",
                    "Name_Type_Code__c": "OFFICIAL"
                },
                {
                    "Id": "N22",
                    "salesforceId": "22",
                    "FirstName__c": "Nana",
                    "LastName__c": "Visitor",
                    "Name_Contact__c": "A2",
                    "Name_Type_Code__c": "LISTING"
                },
                {
                    "Id": "N21",
                    "salesforceId": "21",
                    "FirstName__c": "Nana",
                    "LastName__c": "Tucker",
                    "Name_Contact__c": "A2",
                    "Name_Type_Code__c": "OFFICIAL"
                },
                {
                    "Id": "N32",
                    "salesforceId": "32",
                    "FirstName__c": "JaZahn",
                    "LastName__c": "Clevenger",
                    "Name_Contact__c": "A3",
                    "Name_Type_Code__c": "LISTING"
                },
                {
                    "Id": "N31",
                    "salesforceId": "31",
                    "FirstName__c": "Jazahn",
                    "LastName__c": "Clevenger",
                    "Name_Contact__c": "A3",
                    "Name_Type_Code__c": "OFFICIAL"
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
                },
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
        self.assertEqual(2, len(source_config))
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
    

if __name__ == '__main__':
    unittest.main()