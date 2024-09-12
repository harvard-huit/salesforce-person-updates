import unittest
from unittest import mock, skip

import json

from salesforce import HarvardSalesforce


class HarvardSalesforceTest(unittest.TestCase):

    @mock.patch('salesforce.Salesforce')  
    def setUp(self, mock_connection):

        patcher = mock.patch('salesforce.logger')
        self.mock_logger = patcher.start()
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
        
        self.fakeSFDescribe = { 'fields': [] }
        exampleRecord = {}
        for object_name, object_config in self.fakeConfig.items():
            for field in object_config['fields'].keys():
                exampleRecord['name'] = field
                self.fakeSFDescribe['fields'].append(exampleRecord)

        self.sf.type_data = {
            'Contact': {}
        }

        # creating some sample type_data
        normal_contact_fields = ["FirstName", "LastName", "Email"]
        external_contact_fields = ["EPPN", "HUID"]
        for field in normal_contact_fields:
            self.sf.type_data['Contact'][field] = {
                "type": "string",
                "updateable": True,
                "length": 100,
                "externalId": False,
                "unique": False
            }
        for field in external_contact_fields:
            self.sf.type_data['Contact'][field] = {
                "type": "string",
                "updateable": True,
                "length": 100,
                "externalId": True,
                "unique": False
            }

        # this constructs a single record with all of the fields that are contained in the exampleConfig
        self.exampleSFDescribe = { 'fields': [] }
        exampleRecord = {}
        for object_name, object_config in self.exampleConfig.items():
            for field in object_config['fields'].keys():
                exampleRecord['name'] = field
                self.exampleSFDescribe['fields'].append(exampleRecord)

    def fakeSFDescribeFunction(self):
        return self.fakeSFDescribe
    
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
        self.assertTrue(self.sf.validateConfig(config=self.fakeConfig, dry_run=True))

    def test_validate_example_config(self):
        self.assertTrue(self.sf.validateConfig(config=self.exampleConfig, dry_run=True))

    def test_invalid_config(self):
        self.assertNotEqual(self.sf.validateConfig(config={
            "myObject": {
                "fields": "something"
            }
        }, dry_run=True), True)
        
    def test_check_duplicate_success(self):
        self.sf.sf.query_all.return_value = {
            "records": [{
                'Id': '012345678'
            }]
        }

        response = self.sf.check_duplicate(object_name='Contact', errored_data_objects=[{
            "EPPN": "1234"
        }], dry_run=True)

        self.assertEquals(response, 0)






if __name__ == '__main__':
    unittest.main()
