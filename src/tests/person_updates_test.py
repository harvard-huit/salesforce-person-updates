import json
import os
import unittest
from unittest import mock
from salesforce_person_updates import SalesforcePersonUpdates


class SalesforcePersonUpdatesTest(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch('salesforce_person_updates.logger')
        self.mock_logger = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('salesforce_person_updates.HarvardSalesforce', autospec=True)
        self.mock_hsf = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_hsf_instance = self.mock_hsf.return_value
        self.mock_hsf_instance.type_data = None
        self.mock_hsf_instance.validateConfig.return_value = True

        patcher = mock.patch('salesforce_person_updates.pds')
        self.mock_pds = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_pds_instance = self.mock_pds.People.return_value


        os.environ['FORCE_LOCAL_CONFIG'] = "True"
        self.sfpu = SalesforcePersonUpdates(local="True")

    def test_cleanup_updateds_on_Contacts(self):
        self.mock_hsf_instance.get_all_external_ids.return_value = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
        self.mock_pds_instance.search.return_value = {
            "count": 5,
            "total_count": 5,
            "results": [
                {
                    "personKey": "1"
                },
                {
                    "personKey": "2"
                },
                {
                    "personKey": "3"
                },
                {
                    "personKey": "4"
                },
                {
                    "personKey": "5"
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds(object_name='Contact')

        correct_amount = len(self.mock_hsf_instance.get_all_external_ids.return_value) - len(self.mock_pds_instance.search.return_value['results'])
        self.mock_logger.info.assert_called_with(f"Found {correct_amount} ids in Contact that are no longer updating")


    def test_cleanup_updateds_on_Contacts_no_change(self):
        self.mock_hsf_instance.get_all_external_ids.return_value = ['1', '2', '3', '4', '5']
        self.mock_pds_instance.search.return_value = {
            "count": 5,
            "total_count": 5,
            "results": [
                {
                    "personKey": "1"
                },
                {
                    "personKey": "2"
                },
                {
                    "personKey": "3"
                },
                {
                    "personKey": "4"
                },
                {
                    "personKey": "5"
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds(object_name='Contact')

        correct_amount = len(self.mock_hsf_instance.get_all_external_ids.return_value) - len(self.mock_pds_instance.search.return_value['results'])
        self.mock_logger.info.assert_called_with(f"Found {correct_amount} ids in Contact that are no longer updating")


    def test_cleanup_updateds_on_Affiliation(self):
        self.mock_hsf_instance.get_all_external_ids.return_value = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
        self.mock_pds_instance.search.return_value = {
            "count": 5,
            "total_count": 5,
            "results": [
                {
                    "employeeRoles": [
                        {
                            "personRoleKey": 1
                        }
                    ]
                },
                {
                    "poiRoles": [
                        {
                            "personRoleKey": 2
                        }
                    ]
                },
                {
                    "studentRoles": [
                        {
                            "personRoleKey": 3
                        }
                    ]
                },
                {
                    "employeeRoles": [
                        {
                            "personRoleKey": 4
                        }
                    ]
                },
                {
                    "employeeRoles": [
                        {
                            "personRoleKey": 5
                        }
                    ]
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds(object_name='hed__Affiliation__c')

        correct_amount = len(self.mock_hsf_instance.get_all_external_ids.return_value) - len(self.mock_pds_instance.search.return_value['results'])
        self.mock_logger.info.assert_called_with(f"Found {correct_amount} ids in hed__Affiliation__c that are no longer updating")

    def test_cleanup_updateds_on_Affiliation_no_change(self):
        self.mock_hsf_instance.get_all_external_ids.return_value = ['1', '2', '3', '4', '5']
        self.mock_pds_instance.search.return_value = {
            "count": 5,
            "total_count": 5,
            "results": [
                {
                    "employeeRoles": [
                        {
                            "personRoleKey": 1
                        }
                    ]
                },
                {
                    "poiRoles": [
                        {
                            "personRoleKey": 2
                        }
                    ]
                },
                {
                    "studentRoles": [
                        {
                            "personRoleKey": 3
                        }
                    ]
                },
                {
                    "employeeRoles": [
                        {
                            "personRoleKey": 4
                        }
                    ]
                },
                {
                    "employeeRoles": [
                        {
                            "personRoleKey": 5
                        }
                    ]
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds(object_name='hed__Affiliation__c')

        correct_amount = len(self.mock_hsf_instance.get_all_external_ids.return_value) - len(self.mock_pds_instance.search.return_value['results'])
        self.mock_logger.info.assert_called_with(f"Found {correct_amount} ids in hed__Affiliation__c that are no longer updating")


if __name__ == '__main__':
    unittest.main()