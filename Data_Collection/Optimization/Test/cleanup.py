import logging

import boto3

from utils import cleanup_stacks


logging.basicConfig(level=logging.INFO)


cleanup_stacks(
    cloudformation=boto3.client('cloudformation'),
    account_id=boto3.client("sts").get_caller_identity()["Account"],
    s3=boto3.resource('s3'),
    athena=boto3.client('athena')
)
