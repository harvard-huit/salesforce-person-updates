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

if __name__ == '__main__':
    unittest.main()