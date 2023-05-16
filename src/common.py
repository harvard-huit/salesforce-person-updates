#============================================================================================
# Imports
#============================================================================================
import os
import configparser
import urllib
import json
import boto3

from dotenv import load_dotenv
load_dotenv() 


#============================================================================================
# logging
#============================================================================================

import logging
stack = os.getenv('STACK') or 'developer'
debug = os.getenv('DEBUG') == "True" or False
logging_format = "%(levelname)s %(msg)s"
if stack == 'developer':
    # logging_format = "%(asctime)s %(levelname)s %(name)s %(pathname)s.%(lineno)s %(msg)s"
    logging_format = "%(msg)s"

if debug:
    logging.basicConfig(level=logging.DEBUG, format=logging_format)
else:
    logging.basicConfig(level=logging.INFO, format=logging_format)

logger = logging.getLogger(__name__)


#============================================================================================
# AppConfig
#============================================================================================
class AppConfig():
    def __init__(self, id, table_name):

        self.id = id
        self.name = id
        self.table_name = table_name
        self.salesforce_username = None
        self.pds_query = None
        self.config = None

        self.salesforce_password = None
        self.salesforce_token = None
        self.salesforce_client_key = None
        self.salesforce_client_secret = None

        self.pds_apikey = None
        self.dept_apikey = None


        self.get_config_values()


    def get_config_values(self):
        # table_name = "aais-services-salesforce-person-updates-dev"

        try:
            dynamo = boto3.client('dynamodb')
            response = dynamo.get_item(
                Key={
                    'id': {'S': self.id},
                    'name': {'S': self.name}
                },
                TableName=self.table_name
            )
            if 'Item' in response:
                self.salesforce_username = response.get('Item').get('salesforce_username').get('S')
                self.pds_query = json.loads(response.get('Item').get('pds_query').get('S'))
                self.config = json.loads(response.get('Item').get('transformation_config').get('S'))

                salesforce_password_arn = response.get('Item').get('salesforce_username').get('S')
                salesforce_token_arn = response.get('Item').get('salesforce_username').get('S')
                salesforce_client_key_arn = response.get('Item').get('salesforce_username').get('S')
                salesforce_client_secret_arn = response.get('Item').get('salesforce_username').get('S')

                pds_apikey_arn = None
                dept_apikey_arn = None

            
            else:
                raise Exception(f"Error: unable to retrieve table values for table {self.table_name}: {response}")
        except Exception as e:
            logger.error(f"Error: failure to get configuration for id:{self.id} on table: {self.table_name}")
            raise e
        
        try:
        
            self.salesforce_password = None
            self.salesforce_token = None
            self.salesforce_client_key = None
            self.salesforce_client_secret = None

            self.pds_apikey = None
            self.dept_apikey = None

        except Exception as e:
            logger.error(f"Error: failure to get secrets manager values")    
            raise e
        
    def get_secret(self, arn):
        pass

#============================================================================================
# Other
#============================================================================================

# returns True when the person-updates task is running in the configured 
# TODO: this needs to be tested for fargates
def isTaskRunning():
    
    ecs = boto3.client('ecs')

    metadata_url=os.getenv("ECS_CONTAINER_METADATA_URI_V4")
    f = urllib.request.urlopen(metadata_url)
    metadata = json.loads(f.read())
    
    cluster_name = metadata["Labels"]["com.amazonaws.ecs.cluster"]
    task_family = metadata["Labels"]["com.amazonaws.ecs.task-definition-family"]    

    # list tasks returns tasks that are currently running on the given cluster
    # family refers to the task "family" which is the task definition (sans version)
    mylist = ecs.list_tasks(
        cluster=cluster_name,
        family=task_family,
    )['taskArns']

    # note that it will retrieve itself, so we need to make sure more than one is running
    # to determine if it's "already" running
    if len(mylist) > 1:
        return True
    else:
        return False


#============================================================================================
# Global variables
#============================================================================================

