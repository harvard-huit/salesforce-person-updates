#============================================================================================
# Imports
#============================================================================================
import os
import urllib
import json
import boto3
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv() 


#============================================================================================
# logging
#============================================================================================

import logging
stack = os.getenv('STACK') or 'developer'
debug = os.getenv('DEBUG') == "True" or False
logging_format = "%(levelname)s %(msg)s"

logger = logging.getLogger(__name__)
if debug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
formatter = logging.Formatter(logging_format)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)





#============================================================================================
# AppConfig
#============================================================================================
class AppConfig():
    def __init__(self, id, table_name, local=False):

        self.local = local

        self.id = id
        self.name = id
        self.table_name = table_name
        self.salesforce_username = None
        self.salesforce_domain = None
        self.pds_query = None
        self.config = None
        self.watermarks = {
            "person": None,
            "department": None
        }

        self.salesforce_password = None
        self.salesforce_token = None
        self.salesforce_client_key = None
        self.salesforce_client_secret = None

        self.pds_apikey = None
        self.dept_apikey = None

        # for updates, this is what we'll use for updating the watermark
        self.starting_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # if it's local, we try and populate all of the values from environment variables
        if self.local:
            f = open('../example_config.json')
            self.config = json.load(f)
            f.close()

            f = open('../example_pds_query.json')
            self.pds_query = json.load(f)
            f.close()

            self.pds_apikey = os.getenv('PDS_APIKEY')
            self.dept_apikey = os.getenv('DEPT_APIKEY')

            self.salesforce_username = os.getenv('SF_USERNAME') or None
            self.salesforce_domain = os.getenv('SF_DOMAIN') or "test"
            self.salesforce_password = os.getenv('SF_PASSWORD') or None
            self.salesforce_token = os.getenv('SF_SECURITY_TOKEN') or None
            self.salesforce_client_key = os.getenv('SF_CLIENT_KEY') or None
            self.salesforce_client_secret = os.getenv('SF_CLIENT_SECRET') or None

            one_day_ago = datetime.now() - timedelta(days=1)
            person_watermark_env = os.getenv('PERSON_WATERMARK') or False
            if person_watermark_env:
                person_watermark = datetime.strptime(person_watermark_env, '%Y-%m-%d %H:%M:%S').date()
            else:
                person_watermark = one_day_ago
            department_watermark_env = os.getenv('DEPARTMENT_WATERMARK') or False
            if department_watermark_env:
                department_watermark = datetime.strptime(department_watermark_env, '%Y-%m-%d %H:%M:%S').date()
            else:
                department_watermark = one_day_ago
            self.watermarks = {
                "person": person_watermark,
                "department": department_watermark
            }

        else:
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
                self.salesforce_domain = response.get('Item').get('salesforce_domain').get('S')
                self.pds_query = json.loads(response.get('Item').get('pds_query').get('S'))
                self.config = json.loads(response.get('Item').get('transformation_config').get('S'))

                self.watermarks = response.get('Item').get('watermarks').get('M')
                if os.getenv("FORCE_PERSON_WATERMARK"):
                    self.watermarks["person"] = os.getenv("FORCE_PERSON_WATERMARK")
                if os.getenv("FORCE_DEPARTMENT_WATERMARK"):
                    self.watermarks["department"] = os.getenv("FORCE_DEPARTMENT_WATERMARK")

                # we want the watermarks to be datetime objects so we can do comparisons easily on them
                #   this will also throw an error if the format is wrong on the watermark
                datetime_watermarks = {}
                for index, watermark in self.watermarks.items():
                    datetime_watermarks[index] = datetime.strptime(watermark['S'], '%Y-%m-%d %H:%M:%S').date()
                self.watermarks = datetime_watermarks

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

        if 'SecretString' in response:
            secret_string = response['SecretString']
            if val:
                return json.loads(secret_string).get(val)
            else: 
                return secret_string
        else:
            raise Exception(f"Error: failure to get secret value for {arn}")
    
    def update_watermark(self, watermark_name):
        # we don't want to be trying this if we're using local/developer settings
        if not self.local:
            # change the watermarks back to strings
            string_watermarks = {}
            for index, watermark in self.watermarks.items():
                if index == watermark_name:
                    string_watermarks[index] = self.starting_timestamp
                else:
                    string_watermarks[index] = watermark.strftime('%Y-%m-%d %H:%M:%S')

            try: 
                dynamodb = boto3.resource('dynamodb')
                table = dynamodb.Table(self.table_name)

                table.update_item(
                    Key={
                        'id': self.id,
                        'name': self.name
                    },
                    UpdateExpression='SET watermarks = :val',
                    ExpressionAttributeValues={
                        ':val': string_watermarks
                    }
                )
            except Exception as e:
                logger.error(f"Error: failiure to update dynamo table {self.table_name} with watermarks {string_watermarks}")
                raise e
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

