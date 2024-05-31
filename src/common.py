#============================================================================================
# Imports
#============================================================================================
import os
import urllib
import json
import boto3
import threading
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
            "account": None
        }

        task_info = self.get_task_info()
        if task_info:
            self.task_arn = task_info.get('task_arn')
            self.cluster = task_info.get('cluster')
        else:
            self.task_arn = None
            self.cluster = None


        self.salesforce_password = None
        self.salesforce_token = None
        self.salesforce_client_key = None
        self.salesforce_client_secret = None

        self.pds_apikey = None
        self.dept_apikey = None

        # for updates, this is what we'll use for updating the watermark
        self.starting_timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        if self.local:
            self.set_local_config_values()
        else:
            # if it's not local, we get the config values from the dynamo table
            self.get_config_values()

    # this method just sets all of the config variables 
    #   - this only matters if things are being run locally 
    #   - it removes aws from the dependencies
    def set_local_config_values(self):
        # config and query we'll get from the example json files on the root
        f = open('../example_config.json')
        self.config = json.load(f)
        f.close()

        f = open('../example_pds_query.json')
        self.pds_query = json.load(f)
        f.close()

        # apikeys for the pds and dept (these might be the same, might not)
        self.pds_apikey = os.getenv('PDS_APIKEY')
        self.dept_apikey = os.getenv('DEPT_APIKEY')

        # salesforce credentials
        self.salesforce_username = os.getenv('SF_USERNAME') or None
        self.salesforce_domain = os.getenv('SF_DOMAIN') or "test"
        self.salesforce_password = os.getenv('SF_PASSWORD') or None
        self.salesforce_token = os.getenv('SF_SECURITY_TOKEN') or None
        self.salesforce_client_key = os.getenv('SF_CLIENT_KEY') or None
        self.salesforce_client_secret = os.getenv('SF_CLIENT_SECRET') or None

        # default the watermarks to one day ago if they're not defined (locally)
        #   and ensure they're datetime format
        one_day_ago = datetime.now() - timedelta(days=1)
        person_watermark_env = os.getenv('PERSON_WATERMARK') or False
        if person_watermark_env:
            person_watermark = datetime.strptime(person_watermark_env, '%Y-%m-%dT%H:%M:%S').date()
        else:
            person_watermark = one_day_ago

        account_watermark_env = os.getenv('ACCOUNT_WATERMARK') or False
        if account_watermark_env:
            account_watermark = datetime.strptime(account_watermark_env, '%Y-%m-%dT%H:%M:%S').date()
        else:
            account_watermark = one_day_ago
        
        # set the watermarks the same way they would come out from the get_config_values
        self.watermarks = {
            "person": person_watermark,
            "account": account_watermark
        }


    def get_config_values(self):
            """
            Retrieves configuration values from DynamoDB and secrets manager and sets them as attributes of the object.
            """
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

                    # we want the watermarks to be datetime objects so we can do comparisons easily on them
                    #   this will also throw an error if the format is wrong on the watermark
                    datetime_watermarks = {}
                    for index, watermark in self.watermarks.items():
                        datetime_watermarks[index] = datetime.strptime(watermark['S'], '%Y-%m-%dT%H:%M:%S').date()
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
        elif arn is None:
            return None
        else: 
            logger.warning(f"Warning: arn {arn} is not in the correct format")
            return None
            
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
                    string_watermarks[index] = watermark.strftime('%Y-%m-%dT%H:%M:%S')

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
    
                if watermark_name:
                    return string_watermarks[watermark_name]
                else:
                    return string_watermarks
            except Exception as e:
                logger.error(f"Error: failiure to update dynamo table {self.table_name} with watermarks {string_watermarks}")
                raise e
            
    def get_task_info(self):
        """
        Retrieves info about the ECS task from the environment URI
        """
        try:
            if os.getenv('ECS_CONTAINER_METADATA_URI_V4') is not None:
                metadata_uri = os.getenv('ECS_CONTAINER_METADATA_URI_V4')
                response = urllib.request.urlopen(metadata_uri)
                data = json.loads(response.read())
                logger.info(f"info: ECS_CONTAINER_METADATA_URI_V4 found in environment: {data}")
                cluster = data.get('Cluster')
                task_arn = data.get('TaskARN')
                if task_arn is None:
                    if 'Labels' in data:
                        task_arn = data.get('Labels').get('com.amazonaws.ecs.task-arn')
                return {
                    "task_arn": task_arn,
                    "cluster": cluster
                }
            else:
                logger.info(f"info: ECS_CONTAINER_METADATA_URI_V4 not found in environment, assuming local environment")
                return None
        except Exception as e:
            logger.error(f"Error: failure to get task arn from environment")
            raise e
        
    def stop_task_with_reason(self, reason):
        """
        Stops the task with the given ARN and reason
        """
        if self.task_arn is None:
            logger.warning(f"Warning: task ARN not found, cannot stop task")
            return

        try:
            ecs = boto3.client('ecs')
            ecs.stop_task(
                cluster=self.cluster,
                task=self.task_arn,
                reason=reason
            )
            logger.info(f"Info: Stopping task {self.task_arn} with reason {reason}")
        except Exception as e:
            logger.error(f"Error: failure to stop task {self.task_arn} with reason {reason}")
            raise e


#============================================================================================
# Other
#============================================================================================

# returns True when the person-updates task is running 
def isTaskRunning(app_config: AppConfig):
    """
    Retrieves task running status from DynamoDB 
    """
    task_running = False
    try:
        dynamo = boto3.client('dynamodb')
        response = dynamo.get_item(
            Key={'id': {'S': app_config.id}, 'name': {'S': app_config.name}},
            TableName=app_config.table_name
        )
        if 'Item' in response:
            task_running_attribute = response.get('Item').get('task_running')
            if task_running_attribute:
                task_running = task_running_attribute.get('BOOL',False)
            else:
                setTaskRunning(app_config, False)
        else:
            raise Exception(f"Error: unable to retrieve table values for table {app_config.table_name}: {response}")
    except Exception as e:
        logger.error(f"Error: failure to get task status for id:{id} on table: {app_config.table_name}")
        raise e

    return task_running

# sets the status of the task_running variable
def setTaskRunning(app_config: AppConfig, running: bool):
    """
    Sets task running status in DynamoDB 
    """
    try:
        dynamo = boto3.resource('dynamodb')
        table = dynamo.Table(app_config.table_name)

        update_expression = 'SET task_running = :val1'
        expression_attribute_values = {':val1': running }
        table.update_item(
            Key={'id': app_config.id, 'name': app_config.name},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )
        logger.info(f"Info: Setting task_running variable to {running} for {app_config.name}")
    except Exception as e:
        logger.error(f"Error: failure to set task status for id:{app_config.id} on table: {app_config.table_name}")
        raise e


def get_all_config_ids(table_name):
    """
    Retrieves all config ids from DynamoDB
    """
    try:
        dynamo = boto3.client('dynamodb')
        response = dynamo.scan(TableName=table_name)
        return [item.get('id').get('S') for item in response.get('Items')]
    except Exception as e:
        logger.error(f"Error: failure to get all config ids from table: {table_name}")
        raise e
    
    
class ThreadExcept(threading.Thread):
    def __init__(self, target, args):
        super().__init__(target=target, args=args)
        self.exception = None

    def run(self):
        try:
            if self._target:
                self._target(*self._args)
        except Exception as e:
            self.exception = e