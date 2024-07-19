import boto3
import sys
import json

# get a table_name from a passed in command line arg
table_name = sys.argv[1]

def get_instances(table_name):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    response = table.scan()
    # return the 'id' for each item in the table
    return [item['id'] for item in response['Items']]

print(json.dumps(get_instances(table_name)))