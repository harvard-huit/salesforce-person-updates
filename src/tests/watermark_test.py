import json
import os
import unittest
from unittest import mock
from datetime import datetime
from common import AppConfig




class SalesforcePersonUpdatesTest(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch('common.logger')
        self.mock_logger = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('common.boto3.resource', autospec=True)
        self.mock_boto3_resource = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('common.boto3.client', autospec=True)
        self.mock_boto3_client = patcher.start()
        self.addCleanup(patcher.stop)

        self.mock_config = {
            "Item": {
                "salesforce_username": {
                    "S": "username"
                },
                "salesforce_domain": {
                    "S": "domain"
                },
                "pds_query": {
                    "S": "{}"
                },
                "transformation_config": {
                    "S": "{}"
                },
                "watermarks": {
                    "M": {
                        "person": {
                            "S": "2024-12-06T16:16:09"
                        }
                    }
                },
                "salesforce_password_arn": {
                    "S": ""
                },
                "pds_apikey_arn": {
                    "S": ""
                },
                "dept_apikey_arn": {
                    "S": ""
                },
            }
                                             
        }

        self.salesforce_id = 'fake_id_1'
        self.table_name = 'fake_table_name'
        self.app_config = AppConfig(id=self.salesforce_id, table_name=self.table_name, local=True)


    def test_update_watermark(self):
        dynamo_instance = mock.MagicMock()                                        
        dynamo_instance.execute.return_value = True
        self.mock_boto3_resource.return_value = dynamo_instance
        self.app_config.local = False
        string_watermarks = self.app_config.update_watermark('person')

        self.assertTrue(True)

    def test_get_config(self):
        mock_dynamo = mock.MagicMock()
        self.mock_boto3_client.return_value = mock_dynamo
        mock_dynamo.get_item.return_value = self.mock_config
        snapshot = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        self.mock_config['Item']['watermarks']['M']['person']['S'] = snapshot
        self.app_config.get_config_values()
        watermark = self.app_config.watermarks['person'].strftime('%Y-%m-%dT%H:%M:%S')

        self.assertEqual(watermark, snapshot)

if __name__ == '__main__':
    unittest.main()