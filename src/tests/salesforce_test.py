import unittest
from unittest import mock

import json

from salesforce import HarvardSalesforce


class HarvardSalesforceTest(unittest.TestCase):

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

        self.fakePersonData = [
            {
                "personKey": "2940935f3b990174",
                "eppn": "2940935f3b990174",
                "netid": "jac873",
                "univid": "80719647",
                "uuid": "e9f928bc98814859a3595494e368bbcc",
                "loginName": "jcleveng@fas.harvard.edu",
                "names": [
                    {
                        "personNameKey": 2162790,
                        "personNameType": {
                            "code": "OFFICIAL"
                        },
                        "firstName": "Jazahn",
                        "lastName": "Clevenger",
                        "effectiveStatus": {
                            "code": "A"
                        },
                        "effectiveDate": "2019-03-29T02:50:20",
                        "updateDate": "2019-03-29T02:50:20"
                    },
                    {
                        "personNameKey": 3701467,
                        "personNameType": {
                            "code": "LISTING"
                        },
                        "firstName": "JaZahn",
                        "lastName": "Clevenger",
                        "effectiveStatus": {
                            "code": "A"
                        },
                        "effectiveDate": "2018-10-23T02:32:49",
                        "updateDate": "2018-10-23T02:32:49"
                    }
                ],
                "pronouns": [
                    {
                        "personPronounKey": 5176,
                        "pronouns": "he, him",
                        "securityCategory": {
                            "code": "B"
                        },
                        "privacyValue": {
                            "code": "4"
                        },
                        "effectiveStatus": {
                            "code": "A"
                        },
                        "effectiveDate": "2023-01-09T15:28:24",
                        "updateDate": "2023-01-09T15:28:24"
                    }
                ],
                "employeeRoles": [
                    {
                        "personRoleKey": 1981022,
                        "roleType": {
                            "code": "EMPLOYEE"
                        },
                        "primeRoleIndicator": False,
                        "roleTitle": "DCE Teaching Support",
                        "employmentStatus": {
                            "code": "T",
                            "description": "Terminated"
                        },
                        "hrDeptId": "103623",
                        "hrDeptKey": "103623",
                        "hrDeptDesc": "CADM^HUIT^ATS^App Arch&Int Svc",
                        "hrDeptOfficialDesc": "Applications Architecture and Integration Services",
                        "faculty": {
                            "code": "UIS"
                        },
                        "subAffiliation": {
                            "code": "HUIT_ADMIT^SA",
                            "description": "Administrative IT"
                        },
                        "majAffiliation": {
                            "code": "HUIT^MA",
                            "description": "Harvard University Information"
                        },
                        "updateDate": "2020-10-18T02:32:01",
                        "dwUpdateDate": "2023-04-04T02:03:12"
                    },
                    {
                        "personRoleKey": 2608664,
                        "roleType": {
                            "code": "EMPLOYEE"
                        },
                        "primeRoleIndicator": False,
                        "roleTitle": "DCE Teaching Support",
                        "employmentStatus": {
                            "code": "T",
                            "description": "Terminated"
                        },
                        "hrDeptId": "102662",
                        "hrDeptKey": "102662",
                        "hrDeptDesc": "FAS^FDCE^Other Academic",
                        "hrDeptOfficialDesc": "Division of Continuing Education -Other Academic",
                        "faculty": {
                            "code": "DCE"
                        },
                        "subAffiliation": {
                            "code": "ECS^SA",
                            "description": "ECS Sub-Affiliation"
                        },
                        "majAffiliation": {
                            "code": "FAS^MA",
                            "description": "Fac Arts & Scis Major Affil"
                        },
                        "futureEmp": False,
                        "paidFlag": False,
                        "fulltimeFlag": False,
                        "fullPartTimeManualOverride": "P",
                        "updateDate": "2017-07-02T02:50:00",
                        "dwUpdateDate": "2023-04-04T02:03:12"
                    }
                ],
                "poiRoles": [
                    {
                        "personRoleKey": 3237125,
                        "securityCategory": {
                            "code": "D"
                        },
                        "roleType": {
                            "code": "OTHER"
                        },
                        "primeRoleIndicator": False,
                        "roleTitle": "Unknown",
                        "faculty": {
                            "code": "FAS"
                        },
                        "hrDeptId": 1,
                        "hrDeptKey": None,
                        "hrDeptDesc": None,
                        "hrDeptOfficialDesc": None,
                        "subAffiliation": {
                            "code": None,
                            "description": None
                        },
                        "majAffiliation": {
                            "code": None,
                            "description": None
                        },
                        "updateDate": "2016-11-15T13:25:27"
                    }
                ],
                "cards": [
                    {
                        "personCardKey": 1365952,
                        "univId": "80719647",
                        "effectiveDate": "2007-12-21T02:32:20",
                        "effectiveStatus": {
                            "code": "A"
                        },
                        "reissueDigit": "0",
                        "disableFlag": "N",
                        "updateDate": "2013-03-18T22:16:19"
                    }
                ]
            }
        ]

        self.fakeQueryAllIds = {
            "records": [
                {
                    "Id": "1",
                    "salesforceId": "2940935f3b990174"
                },
                {
                    "Id": "2",
                    "salesforceId": "a2"
                },
                {
                    "Id": "3",
                    "salesforceId": "a3"
                }
            ]
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

    
    # Just test to make sure the mock created the HarvardSalesforce object
    def test_mock(self):
        self.assertIsInstance(self.sf, HarvardSalesforce)

    def test_get_unique_ids(self):
        self.sf.sf.query_all.return_value = self.fakeQueryAllIds

        hashed_ids = self.sf.getUniqueIds(config=self.fakeConfig, source_data=self.fakePersonData)
        self.assertIn('Contact', hashed_ids)
        self.assertIn('Ids', hashed_ids['Contact'])
        self.assertIn('2940935f3b990174', hashed_ids['Contact']['Ids'])
        self.assertEqual(hashed_ids['Contact']['Ids']["2940935f3b990174"], "1")        
        
    def test_fail_get_unique_ids(self):
        self.sf.sf.query_all.return_value = self.fakeQueryAllIds

        hashed_ids = self.sf.getUniqueIds(config=self.fakeConfig, source_data=self.fakePersonData)
        self.assertIn('Contact', hashed_ids)
        self.assertIn('Ids', hashed_ids['Contact'])
        self.assertIn('2940935f3b990174', hashed_ids['Contact']['Ids'])

    def test_validate_config(self):
        self.sf.sf.query_all.return_value = self.fakeSFData
        self.assertTrue(self.sf.validateConfig(self.fakeConfig))

    def test_validate_example_config(self):
        self.sf.sf.query_all.return_value = self.exampleSFData
        self.assertTrue(self.sf.validateConfig(self.exampleConfig))

    def test_invalid_config(self):
        self.sf.sf.query_all.return_value = self.exampleSFData
        self.assertFalse(self.sf.validateConfig({
            "myObject": {
                "fields": "something"
            }
        }))
        

if __name__ == '__main__':
    unittest.main()