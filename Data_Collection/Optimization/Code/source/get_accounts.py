import boto3
import logging
import os
import json

logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % numeric_level)
    logger.setLevel(level=numeric_level)
else:
    logger.setLevel(logging.INFO)


def org_accounts(role_name, payer_id):
    account_ids = []
    ROLE_ARN = f"arn:aws:iam::{payer_id}:role/{role_name}"
    sts_connection = boto3.client('sts')
    acct_b = sts_connection.assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName="data_collection"
    )
            
    ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
    SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
    SESSION_TOKEN = acct_b['Credentials']['SessionToken']

    # create service client using the assumed role credentials
    client = boto3.client(
        "organizations", region_name="us-east-1", #Using the Organization client to get the data. This MUST be us-east-1 regardless of region you have the lamda in
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        aws_session_token=SESSION_TOKEN,
    )
    paginator = client.get_paginator("list_accounts") #Paginator for a large list of accounts
    response_iterator = paginator.paginate()

    for account in response_iterator:
        for ids in account['Accounts']:
            account_ids.append(ids)
    logger.info("AWS Org data Gathered")
    return account_ids


def lambda_handler(event, context):
    role_name = os.environ['ROLE']
    MANAGEMENT_ACCOUNT_IDS = os.environ['MANAGEMENT_ACCOUNT_IDS']

    accountlist = []
    for payer_id in [r.strip() for r in MANAGEMENT_ACCOUNT_IDS.split(',')]:
        try: 
            account_info = org_accounts(role_name, payer_id)
            
            for account in account_info:
                if  account['Status'] == 'ACTIVE':
                    try:
                        account_data = {}
                        account_data['account_id'] = account['Id']
                        account_data['account_name'] = account['Name']
                        account_data['payer_id'] = payer_id

                        accountlist.append({"account" : json.dumps(account_data)})
                    except Exception as e:
                        logger.warning("%s" % e)
                else:
                    logger.info(f"account {account['Id']} is not active")
            logger.info(f"AWS Org data gathered and found {len(accountlist)} accounts")
        except Exception as e:
            # Send some context about this error to Lambda Logs
            logger.warning("%s" % e)
            continue 
    if len(accountlist) == 0:
        raise ValueError("No accounts were collected.")
    return {
        'statusCode': 200,
        'accountList': accountlist
    }