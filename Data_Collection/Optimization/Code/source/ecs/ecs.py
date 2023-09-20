import boto3
from boto3.session import Session
import logging
from datetime import date, datetime
import json
import os
from botocore.exceptions import ClientError

bucket = os.environ["BUCKET_NAME"]
prefix = os.environ["PREFIX"]
role_name = os.environ['ROLENAME']

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
        list_region = list_regions()
        local_file = "/tmp/data.json"
        f = open(local_file, "w")
        session = assume_session(account_id)
        for region in list_region:
            logger.info(f"Region is: {region}")
            client = session.client("ecs", region_name = region)
            paginator = client.get_paginator("list_clusters")
            response_iterator = paginator.paginate()

            try:
                for response in response_iterator:
                    for cluster in response["clusterArns"]:
                        listservices = client.list_services(
                            cluster=cluster.split("/")[1],
                            maxResults=100
                        )
                        for i in listservices["serviceArns"]:
                            # print (i)
                            services = client.describe_services(
                                cluster=cluster.split("/")[1],
                                services=[i.split("/")[2],],
                                include=["TAGS"],
                            )
                            for service in services["services"]:
                                data = {
                                    "cluster": cluster.split("/")[1],
                                    "services": service.get("serviceName"),
                                    "servicesARN": i, #.split("/")[2]
                                    "tags": service.get("tags"),
                                    "account_id":account_id
                                }
                                jsondata = json.dumps(data)
                                print(jsondata)
                                f.write(jsondata + "\n")
            except Exception as e:
                print(region, account_id, type(e), e)
            print("respose gathered")
            f.close()

            if os.path.getsize(local_file) == 0:
                print(f"No data in file for {prefix}")
                continue
            today = date.today()
            year = today.year
            month = today.month
            day = today.day
            key = f"{prefix}/{prefix}-data/payer_id={payer_id}/year={year}/month={month}/{account_id}-{year}-{month}-{day}.json"
            client = boto3.client("s3")
            client.upload_file(local_file, bucket, key)
            print(f"Data in s3 - {key}")
    except Exception as e:
        logging.warning(e)
        
def assume_session(account_id):
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}" #OrganizationAccountAccessRole
    sts_client = boto3.client('sts')
    
    try:
        #region = sts_client.meta.region_name
        assumedRoleObject = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="data_collection"
        )
        
        credentials = assumedRoleObject['Credentials']
        session = Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken']
        )
        return session

    except ClientError as e:
        logging.warning(f"Unexpected error Account {account_id}: {e}")
        return None

def list_regions():
    s = Session()
    ecs_regions = s.get_available_regions('ecs')
    return ecs_regions    