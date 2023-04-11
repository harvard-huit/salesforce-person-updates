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

import logging
stack = os.getenv('STACK') or 'developer'
logging_format = "%(levelname)s %(msg)s"
if stack == 'developer':
    logging_format = "%(asctime)s %(levelname)s %(name)s %(pathname)s.%(lineno)s %(msg)s"

logging.basicConfig(level=logging.INFO, format=logging_format)
logger = logging.getLogger(__name__)


#============================================================================================
# Utility Functions
#============================================================================================

#============================================================================================
# AWS Functions
#============================================================================================

#============================================================================================
# get data from DynamoDB
#============================================================================================
def getConfig(nameStr):
    dynamo = boto3.client('dynamodb')
    retValue = dynamo.get_item(
        Key={
            'name': {'S': nameStr}
        },
        TableName="salesforce-person-updates-config",
    )    
    if retValue.get('Item') == None:
        return False
    else:
        return retValue.get('Item').get('flag_value').get('BOOL')

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

