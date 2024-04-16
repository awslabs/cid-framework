import os
import json
import uuid
import urllib3
import boto3

database_name = os.environ['DATABASE_NAME']
resource_prefix = os.environ['RESOURCE_PREFIX']

def lambda_handler(event, context): #pylint: disable=unused-argument
    print(json.dumps(event))
    try:
        action = event.get('RequestType').upper()
        if action not in ['CREATE', 'UPDATE', 'DELETE']:
            raise Exception(f"Unknown RequestType {action}") #pylint: disable=broad-exception-raised
        func = {'CREATE': create, 'DELETE': delete, 'UPDATE': update}.get(action)
        res, reason = func()
    except Exception as exc: #pylint: disable=broad-exception-caught
        if 'Insufficient Lake Formation permission' in str(exc):
            res, reason = 'FAILED', 'Lake Formation is not supported yet. Please use account without Lake Formation.'
        else:
            res, reason = 'FAILED', str(exc)
    body = {
        'Status': res,
        'Reason': reason,
        'PhysicalResourceId': event.get('PhysicalResourceId', str(uuid.uuid1())),
        'StackId': event.get('StackId'),
        'RequestId': event.get('RequestId'),
        'LogicalResourceId': event.get('LogicalResourceId'),
        'NoEcho': False,
        'Data':  {'Reason': reason},
    }
    json_body=json.dumps(body)
    print(json_body)
    url = event.get('ResponseURL')
    if not url:
        return
    try:
        response = urllib3.PoolManager().request('PUT', url, body=json_body, headers={'content-type' : '', 'content-length' : str(len(json_body))}, retries=False)
        print(f"Status code: {response}")
    except Exception as exc: #pylint: disable=broad-exception-caught
        print("Failed sending PUT to CFN: " + str(exc))

def create():
    create_glue_database()
    return  'SUCCESS', 'success'

def update():
    return  'SUCCESS', 'nothing to do'

def delete():
    return  'SUCCESS', 'nothing to do'

def create_glue_database():
    glue_client = boto3.client('glue')
    try:
        glue_client.get_database(Name=database_name)
    except glue_client.exceptions.EntityNotFoundException:
        glue_client.create_database(DatabaseInput={'Name': database_name})
        print(f"Created database '{database_name}'")
    else:
        # Delete all tables updated by previous versions of crawlers.
        # If not crawler will not be able to update the table and will create a new one with a random name.
        for table in glue_client.get_paginator('get_tables').paginate(DatabaseName=database_name).search('TableList'):
            table_name = table.get('Name')
            updated_by = table.get('Parameters', {}).get('UPDATED_BY_CRAWLER', '')
            if not updated_by.startswith(resource_prefix):
                glue_client.delete_table(DatabaseName=database_name, Name=table_name)
                print(f'table {table_name} was deleted to avoid crawler confusion')
    return 'SUCCESS', 'success'