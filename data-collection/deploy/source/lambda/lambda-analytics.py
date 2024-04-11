import os
import json
import uuid
import urllib3
import boto3

endpoint = os.environ['CID_ANALYTICS_ENDPOINT']
account_id = boto3.client("sts").get_caller_identity()["Account"]

def lambda_handler(event, context):  #pylint: disable=unused-argument
    print(json.dumps(event))
    try:
        if event['RequestType'].upper() not in ['CREATE', 'UPDATE', 'DELETE']:
            raise Exception(f"Unknown RequestType {event['RequestType']}") #pylint: disable=broad-exception-raised
        action = event['RequestType'].upper()
        name = event['ResourceProperties']['Name']
        method = {'CREATE':'PUT', 'UPDATE': 'PATCH', 'DELETE': 'DELETE'}.get(action)
        via_key = {'CREATE':'created_via', 'UPDATE': 'updated_via', 'DELETE': 'deleted_via'}.get(action)
        payload = {'id': 'data-collection-lab/' + name, 'account_id': account_id, via_key: 'CFN'}
        r =  urllib3.PoolManager().request(method, endpoint, body=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        if r.status != 200:
            raise Exception(f"There has been an issue logging action, server did not respond with a 200 response, actual status: {r.status}, response data {r.data.decode('utf-8')}. This issue will be ignored") #pylint: disable=broad-exception-raised
        res, reason = 'SUCCESS', 'success'
    except Exception as exc: #pylint: disable=broad-exception-caught
        res, reason = 'SUCCESS', f"{exc} . This issue will be ignored"
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