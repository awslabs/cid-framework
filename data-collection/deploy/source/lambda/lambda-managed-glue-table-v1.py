import os
import json
import uuid
import urllib3
import boto3

database_name = os.environ['DATABASE_NAME']
resource_prefix = os.environ['RESOURCE_PREFIX']
glue_client = boto3.client('glue')

def lambda_handler(event, context): #pylint: disable=unused-argument
    print(json.dumps(event))
    try:
        action = event.get('RequestType').upper()
        if action not in ['CREATE', 'UPDATE', 'DELETE']:
            raise Exception(f"Unknown RequestType {action}") #pylint: disable=broad-exception-raised
        func = {'CREATE': create_or_update, 'DELETE': delete, 'UPDATE': create_or_update}.get(action)
        table_input = event['ResourceProperties']['TableInput']
        res, reason = func(table_input)
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

def create_or_update(table_input):
    try:
        glue_client.create_table(DatabaseName=database_name, TableInput=table_input)
        return  'SUCCESS', 'created'
    except glue_client.exceptions.AlreadyExistsException:
        glue_client.update_table(DatabaseName=database_name, TableInput=table_input)
        return  'SUCCESS', 'updated'

def delete(table_input):
    try:
        glue_client.delete_table(DatabaseName=database_name, Name=table_input['Name'])
        return  'SUCCESS', 'deleted'
    except glue_client.exceptions.EntityNotFoundException:
        return  'SUCCESS', 'not found'