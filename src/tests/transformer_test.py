import unittest
from unittest import mock
import json

from transformer import SalesforceTransformer
from salesforce import HarvardSalesforce

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
                    "Birthdate": "birthDate",
                    "FirstName": {
                        "value": "names.firstName",
                        "when": {
                            "names.personNameType.code": ["LISTING", "OFFICIAL"]
                        }
                    }
                }
            },
            "somethingelse": {
                "flat": False,
                "source": "departments",
                "Id": {
                    "departments": "personKey",
                    "salesforce": "salesforceId"
                },
                "fields": {
                    "personKey": "personKey",
                    "Birthdate": "birthdate"
                }
            }
        }

        self.fakeSFData = {
            'records': [
                {
                    'Id': 'A1',
                    'personKey': '1',
                    "Birthdate": "birthDate",
                    "FirstName": "me"

                },
                {
                    'Id': 'A2',
                    'personKey': '2',
                    "Birthdate": "birthDate",
                    "FirstName": "me"
                }
            ]
        }

        self.sample_when = {
            "names.personNameType.code": ["LISTING", "OFFICIAL"]
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


        # this constructs a single record with all of the fields that are contained in the exampleConfig
        self.exampleSFData = { 'records': [] }
        exampleRecord = {}
        for object_name, object_config in self.exampleConfig.items():
            for field in object_config['fields'].keys():
                exampleRecord[field] = "junk data"
        self.exampleSFData['records'].append(exampleRecord)

        self.transformer = SalesforceTransformer(config=self.fakeConfig, hsf=self.sf)

    def test_validate_sample_configs(self):
        self.sf.sf.query_all.return_value = self.fakeSFData
        self.assertTrue(self.sf.validateConfig(self.fakeConfig))
        self.sf.sf.query_all.return_value = self.exampleSFData
        self.assertTrue(self.sf.validateConfig(self.exampleConfig))

    def test_validate_source_config_split(self):
        self.sf.sf.query_all.return_value = self.fakeSFData
        self.transformer.config = self.fakeConfig
        source_config = self.transformer.getSourceConfig('pds')
        self.assertTrue(self.sf.validateConfig(source_config))
        self.assertEqual(1, len(source_config))
        for object_name in source_config:
            self.assertEqual('pds', source_config[object_name]['source'])

    def test_validate_target_config_split(self):
        self.sf.sf.query_all.return_value = self.fakeSFData
        self.transformer.config = self.fakeConfig
        target_config = self.transformer.getTargetConfig('Contact')
        self.assertTrue(self.sf.validateConfig(target_config))
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


if __name__ == '__main__':
    unittest.main()