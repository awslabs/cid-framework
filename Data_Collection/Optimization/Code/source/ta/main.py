import os
import json
from datetime import date, datetime
from json import JSONEncoder

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import logging

prefix = os.environ["PREFIX"]
bucket = os.environ["BUCKET_NAME"]
role_name = os.environ['ROLENAME']
costonly = os.environ.get('COSTONLY', 'no').lower() == 'yes'

logger = logging.getLogger()
if "LOG_LEVEL" in os.environ:
    numeric_level = getattr(logging, os.environ['LOG_LEVEL'].upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % numeric_level)
    logger.setLevel(level=numeric_level)
else:
    logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    collection_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if 'account' not in event:
        raise ValueError(
            "Please do not trigger this Lambda manually."
            "Find the corresponding state machine in Step Functions and Trigger from there."
        )
    
    try:
        account = json.loads(event["account"])
        account_id = account["account_id"]
        account_name = account["account_name"]
        payer_id = account["payer_id"]
        logger.info(f"Collecting data for account: {account_id}")
        f_name = "/tmp/data.json"
        read_ta(account_id, account_name, f_name)
        upload_to_s3(prefix, account_id, payer_id, f_name)
    except Exception as e:
        logging.warning(e)

def upload_to_s3(prefix, account_id, payer_id, f_name):
    if os.path.getsize(f_name) == 0:
        print(f"No data in file for {prefix}")
        return
    d = datetime.now()
    month = d.strftime("%m")
    year = d.strftime("%Y")
    _date = d.strftime("%d%m%Y-%H%M%S")
    path = f"{prefix}/{prefix}-data/payer_id={payer_id}/year={year}/month={month}/{prefix}-{account_id}-{_date}.json"
    try:
        s3 = boto3.client("s3", config=Config(s3={"addressing_style": "path"}))
        s3.upload_file(f_name, bucket, path )
        print(f"Data for {account_id} in s3 - {path}")
    except Exception as e:
        print(f"{type(e)}: {e}")

def assume_role(account_id, service, region, role):
    assumed = boto3.client('sts').assume_role(RoleArn=f"arn:aws:iam::{account_id}:role/{role}", RoleSessionName='data_collection')
    creds = assumed['Credentials']
    return boto3.client(service, region_name=region,
        aws_access_key_id=creds['AccessKeyId'],
        aws_secret_access_key=creds['SecretAccessKey'],
        aws_session_token=creds['SessionToken'],
    )

def _json_serial(self, obj):
    if isinstance(obj, (datetime, date)): return obj.isoformat()
    return JSONEncoder.default(self, obj)

def read_ta(account_id, account_name, f_name):
    f = open(f_name, "w")
    support = assume_role(account_id, "support", "us-east-1", role_name)
    checks = support.describe_trusted_advisor_checks(language="en")["checks"]
    for check in checks:
        #print(json.dumps(check))
        if (costonly and check.get("category") != "cost_optimizing"): continue
        try:
            result = support.describe_trusted_advisor_check_result(checkId=check["id"], language="en")['result']
            #print(json.dumps(result))
            if result.get("status") == "not_available": continue
            dt = result['timestamp']
            ts = datetime.strptime(dt, '%Y-%m-%dT%H:%M:%SZ').strftime('%s')
            for resource in result["flaggedResources"]:
                output = {}
                if "metadata" in resource:
                    output.update(dict(zip(check["metadata"], resource["metadata"])))
                    del resource['metadata']
                resource["Region"] = resource.pop("region") if "region" in resource else '-'
                resource["Status"] = resource.pop("status") if "status" in resource else '-'
                output.update({"AccountId":account_id, "AccountName":account_name, "Category": check["category"], 'DateTime': dt, 'Timestamp': ts, "CheckName": check["name"], "CheckId": check["id"]})
                output.update(resource)
                f.write(json.dumps(output, default=_json_serial) + "\n")
        except Exception as e:
            print(f'{type(e)}: {e}')