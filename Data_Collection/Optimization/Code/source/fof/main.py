""" Scan linked accounts and store instances info to s3 bucket
Supported types: ebs, snapshots, ami, rds instances
"""
import os
import json
from functools import partial, lru_cache
from datetime import datetime, date

import boto3
from botocore.client import Config
import logging

TMP_FILE = "/tmp/data.json"
PREFIX = os.environ['PREFIX']
BUCKET = os.environ["BUCKET_NAME"]
ROLENAME = os.environ['ROLENAME']


logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % numeric_level)
    logger.setLevel(level=numeric_level)
else:
    logger.setLevel(logging.INFO)

def to_json(obj):
    """json helper for date time data"""
    return json.dumps(
        obj,
        default=lambda x:
            x.isoformat() if isinstance(x, (date, datetime)) else None
    )

@lru_cache(maxsize=10000)
def assume_session(account_id):
    """assume role in account"""
    credentials = boto3.client('sts').assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{ROLENAME}" ,
        RoleSessionName="data_collection"
    )['Credentials']
    return boto3.session.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )

@lru_cache(maxsize=10000)
def enabled_regions(session):
    """list enabled regions"""
    return set(reg['RegionName'] for reg in session.client('ec2').describe_regions()['Regions'])

def paginated_scan(service, account_id, function_name, params=None, obj_name=None):
    """ paginated scan """
    session = assume_session(account_id)
    regions = set(session.get_available_regions(service)) & enabled_regions(session)
    obj_name = obj_name or function_name.split('_')[-1].capitalize()
    for region in regions:
        logger.info(f"Collecting {service}.{obj_name} in {region}")
        client = session.client(service, region_name=region)
        try:
            paginator = client.get_paginator(function_name)
            for page in paginator.paginate(**(params or {})):
                for obj in page[obj_name]:
                    obj['region'] = region
                    obj['accountid'] = account_id
                    yield obj
        except Exception as exc:  #pylint: disable=broad-exception-caught
            logger.info(f'scan {function_name}/{account_id}:', exc)

def lambda_handler(event, context): #pylint: disable=unused-argument
    """ this lambda collects ami, snapshots and volumes from linked accounts
    and must be called from the corresponding Step Function to orchestrate
    """
    collection_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if 'account' not in event:
        raise ValueError(
            "Please do not trigger this Lambda manually."
            "Find the corresponding state machine in Step Functions and Trigger from there."
        )

    sub_modules = {
        # 'rds_instances': [
        #     partial(
        #         paginated_scan,
        #         service='rds',
        #         function_name='describe_db_instances',
        #         obj_name='DBInstances'
        #     )
        # ],
        'ebs': partial(
                paginated_scan,
                service='ec2',
                function_name='describe_volumes'
        ),
        'ami': partial(
                paginated_scan,
                service='ec2',
                function_name='describe_images',
                params={'Owners': ['self']}
        ),
        'snapshot': partial(
                paginated_scan,
                service='ec2',
                function_name='describe_snapshots',
                params={'OwnerIds': ['self']}
        )
    }

    account = json.loads(event["account"])
    account_id = account["account_id"]
    payer_id = account["payer_id"]
    for name, (func) in sub_modules.items():
        counter = 0
        logger.info(f"\nCollecting {name} in account {account_id}")
        try:
            with open(TMP_FILE, "w", encoding='utf-8') as file_:
                for counter, obj in enumerate(func(account_id=account_id), start=1):
                    #logger.info(obj) # for debug
                    file_.write(to_json(obj) + "\n")
            logger.info(f"Collected {counter} {name} instances")
            upload_to_s3(name, account_id, payer_id)
        except Exception as exc:   #pylint: disable=broad-exception-caught
            logger.info(f"{name}: {type(exc)} - {exc}" )

def upload_to_s3(name, account_id, payer_id):
    """upload"""
    if os.path.getsize(TMP_FILE) == 0:
        logger.info(f"No data in file for {name}")
        return
    key =  datetime.now().strftime(
        f"{PREFIX}/{PREFIX}-{name}-data/payer_id={payer_id}"
        f"/year=%Y/month=%m/{account_id}-%d%m%Y-%H%M%S.json"
    )
    s3client = boto3.client("s3", config=Config(s3={"addressing_style": "path"}))
    try:
        s3client.upload_file(TMP_FILE, BUCKET, key)
        logger.info(f"Data {account_id} in s3 - {BUCKET}/{key}")
    except Exception as exc:  #pylint: disable=broad-exception-caught
        logger.info(exc)