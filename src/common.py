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

                salesforce_password_arn = response.get('Item').get('salesforce_password_arn').get('S')

                salesforce_token_arn = None
                if 'salesforce_token_arn' in response.get('Item'):
                    salesforce_token_arn = response.get('Item').get('salesforce_token_arn').get('S')

                salesforce_client_key_arn = None
                if 'salesforce_client_key_arn' in response.get('Item'):
                    salesforce_client_key_arn = response.get('Item').get('salesforce_client_key_arn').get('S')
                    
                salesforce_client_secret_arn = None
                if 'salesforce_client_secret_arn' in response.get('Item'):
                    salesforce_client_secret_arn = response.get('Item').get('salesforce_client_secret_arn').get('S')

                pds_apikey_arn = response.get('Item').get('pds_apikey_arn').get('S')
                dept_apikey_arn = response.get('Item').get('dept_apikey_arn').get('S')

            
            else:
                raise Exception(f"Error: unable to retrieve table values for table {self.table_name}: {response}")
        except Exception as e:
            logger.error(f"Error: failure to get configuration for id:{self.id} on table: {self.table_name}")
            raise e
        
        try:
        
            self.salesforce_password = self.get_secret(salesforce_password_arn)
            if salesforce_token_arn:
                self.salesforce_token = self.get_secret(salesforce_token_arn)
            if salesforce_client_key_arn:
                self.salesforce_client_key = self.get_secret(salesforce_client_key_arn)
            if salesforce_client_secret_arn:
                self.salesforce_client_secret = self.get_secret(salesforce_client_secret_arn)

            self.pds_apikey = self.get_secret(pds_apikey_arn)
            self.dept_apikey = self.get_secret(dept_apikey_arn)

        except Exception as e:
            logger.error(f"Error: failure to get secrets manager values")    
            raise e
        
    def get_secret(self, arn):
        secretsmanager = boto3.client('secretsmanager')
        if ':' in arn:
            pieces = arn.split(':')
            arn = ':'.join(pieces[:7])
            val = pieces[-3]
            
        response = secretsmanager.get_secret_value(
            SecretId=arn
        )
        logger.info(f"secretsmanager response: {response}")
        if 'SecretString' in response:
            secret_string = response['SecretString']
            if val:
                return json.loads(secret_string).get(val)
            else: 
                return secret_string
        else:
            raise Exception(f"Error: failure to get secret value for {arn}")
        
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

