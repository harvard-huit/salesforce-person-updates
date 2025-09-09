import json
import os
import unittest
from unittest import mock, skip
from salesforce_person_updates import SalesforcePersonUpdates, logger


class SalesforcePersonUpdatesTest(unittest.TestCase):

    def _get_ids_side_effect(self, object_name, **kwargs):
        if object_name == 'Contact':
            return ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
        elif object_name == 'hed__Affiliation__c':
            return ['11', '12', '13', '14', '15']
        else:
            return []

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
        # unset the updatedFlag for anything but Contact
        # for obj in self.sfpu.app_config.config.keys():
        #     if obj != 'Contact' and 'updatedFlag' in self.sfpu.app_config.config[obj]:
        #         self.sfpu.app_config.config[obj].pop('updatedFlag')
        
        self.mock_hsf_instance.get_all_external_ids.side_effect = self._get_ids_side_effect
        contact_values = self._get_ids_side_effect('Contact')
        self.mock_pds_instance.search.return_value = {
            "count": 5,
            "total_count": 5,
            "results": [
                {
                    "personKey": "1",
                    "employeeRoles": [
                        {
                            "personRoleKey": 11
                        }
                    ]
                },
                {
                    "personKey": "2",
                    "poiRoles": [
                        {
                            "personRoleKey": 12
                        }
                    ]
                },
                {
                    "personKey": "3",
                    "studentRoles": [
                        {
                            "personRoleKey": 13
                        }
                    ]
                },
                {
                    "personKey": "4",
                    "employeeRoles": [
                        {
                            "personRoleKey": 14
                        }
                    ]
                },
                {
                    "personKey": "5",
                    "employeeRoles": [
                        {
                            "personRoleKey": 15
                        }
                    ]
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds()

        correct_amount = len(contact_values) - len(self.mock_pds_instance.search.return_value['results'])
        # self.mock_logger.info.assert_called_with(f"No hed__Affiliation__c records to update")

        info_calls = self.mock_logger.info.call_args_list
        messages = [call[0][0] for call in info_calls]
        self.assertIn(f"Found {correct_amount} ids in Contact that are no longer updating", messages)
        # assert len(info_calls) >= 2
        # last_msg = info_calls[-1][0][0]
        # second_last_msg = info_calls[-2][0][0]
        # # You can now assert on both messages
        # assert last_msg == f"No hed__Affiliation__c records to update"


    # @skip("Skipping for funs")
    def test_cleanup_updateds_on_Contacts_no_change(self):
        # unset the updatedFlag for anything but Contact
        for obj in self.sfpu.app_config.config.keys():
            if obj != 'Contact' and 'updatedFlag' in self.sfpu.app_config.config[obj]:
                self.sfpu.app_config.config[obj].pop('updatedFlag')
        
        self.mock_hsf_instance.get_all_external_ids.side_effect = self._get_ids_side_effect
        contact_values = self._get_ids_side_effect('Contact')
        self.mock_pds_instance.search.return_value = {
            "count": 10,
            "total_count": 10,
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
                },
                {
                    "personKey": "6"
                },
                {
                    "personKey": "7"
                },
                {
                    "personKey": "8"
                },
                {
                    "personKey": "9"
                },
                {
                    "personKey": "10"
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds()
        # assert search is called 1 time
        assert self.mock_pds_instance.search.call_count == 1

        correct_amount = len(self._get_ids_side_effect('Contact')) - len(self.mock_pds_instance.search.return_value['results'])
        # self.mock_logger.info.assert_called_with(f"Found {correct_amount}/{len(self.mock_hsf_instance.get_all_external_ids.return_value)} ids in Contact that are no longer updating")


    # @skip("Skipping for funs")
    def test_cleanup_updateds_on_Affiliation(self):
        self.mock_hsf_instance.get_all_external_ids.side_effect = self._get_ids_side_effect
        self.mock_pds_instance.search.return_value = {
            "count": 10,
            "total_count": 10,
            "results": [
                {
                    "personKey": "1",
                    "employeeRoles": [
                        {
                            "personRoleKey": 11
                        }
                    ]
                },
                {
                    "personKey": "2",
                    "poiRoles": [
                        {
                            "personRoleKey": 12
                        }
                    ]
                },
                {
                    "personKey": "3"
                },
                {
                    "personKey": "4"
                },
                {
                    "personKey": "5"
                },
                {
                    "personKey": "6"
                },
                {
                    "personKey": "7"
                },
                {
                    "personKey": "8"
                },
                {
                    "personKey": "9"
                },
                {
                    "personKey": "10"
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds()

        correct_amount = len(self._get_ids_side_effect('hed__Affiliation__c')) - 2
        self.mock_logger.info.assert_called_with(f"Found {correct_amount} ids in hed__Affiliation__c that are no longer updating")


    def test_cleanup_updateds_on_Affiliation_no_change(self):
        self.mock_hsf_instance.get_all_external_ids.side_effect = self._get_ids_side_effect
        self.mock_pds_instance.search.return_value = {
            "count": 10,
            "total_count": 10,
            "results": [
                {
                    "personKey": "1",
                    "employeeRoles": [
                        {
                            "personRoleKey": 11
                        }
                    ]
                },
                {
                    "personKey": "2",
                    "poiRoles": [
                        {
                            "personRoleKey": 12
                        }
                    ]
                },
                {
                    "personKey": "3",
                    "studentRoles": [
                        {
                            "personRoleKey": 13
                        }
                    ]
                },
                {
                    "personKey": "4",
                    "employeeRoles": [
                        {
                            "personRoleKey": 14
                        }
                    ]
                },
                {
                    "personKey": "5",
                    "employeeRoles": [
                        {
                            "personRoleKey": 15
                        }
                    ]
                },
                {
                    "personKey": "6"
                },
                {
                    "personKey": "7"
                },
                {
                    "personKey": "8"
                },
                {
                    "personKey": "9"
                },
                {
                    "personKey": "10"
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        self.sfpu.cleanup_updateds()

        correct_amount = len(self._get_ids_side_effect('hed__Affiliation__c')) - 5
        self.mock_logger.info.assert_called_with(f"No hed__Affiliation__c records to update")


    def test_cleanup_updateds_on_Affiliation_no_Contact(self):

        self.mock_hsf_instance.get_all_external_ids.side_effect = self._get_ids_side_effect
        self.mock_pds_instance.search.return_value = {
            "count": 10,
            "total_count": 10,
            "results": [
                {
                    "personKey": "1",
                    "employeeRoles": [
                        {
                            "personRoleKey": 11
                        }
                    ]
                },
                {
                    "personKey": "2",
                    "poiRoles": [
                        {
                            "personRoleKey": 12
                        }
                    ]
                },
                {
                    "personKey": "3"
                },
                {
                    "personKey": "4"
                },
                {
                    "personKey": "5"
                },
                {
                    "personKey": "6"
                },
                {
                    "personKey": "7"
                },
                {
                    "personKey": "8"
                },
                {
                    "personKey": "9"
                },
                {
                    "personKey": "10"
                }
            ]
        }
        self.mock_hsf_instance.flag_field.return_value = True

        # unset the updatedFlag for Contact
        config_with_flag = self.sfpu.app_config.config['Contact'].copy()
        if 'updatedFlag' in self.sfpu.app_config.config['Contact']:
            self.sfpu.app_config.config['Contact'].pop('updatedFlag')
        self.sfpu.cleanup_updateds()
        # reset the config so it doesn't mess up other tests
        self.sfpu.app_config.config['Contact'] = config_with_flag


        correct_amount = len(self._get_ids_side_effect('hed__Affiliation__c')) - 2
        self.mock_logger.info.assert_called_with(f"Found {correct_amount} ids in hed__Affiliation__c that are no longer updating")


if __name__ == '__main__':
    unittest.main()