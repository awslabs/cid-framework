''' cleanup test environment
'''
import logging

import boto3

from utils import cleanup_stacks, PREFIX

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    cloudformation = boto3.client('cloudformation')

    # Sometimes cloud formation deletes a role needed for management of stacksets. For these cases we can create just this role. If it exists stack will fail, but it is ok.
    try:
        cloudformation.delete_stack(StackName='TempDebugCIDStackSets')
        cloudformation.create_stack(
            TemplateBody=open('data-collection/test/debugstackets.yml').read(),
            StackName='TempDebugCIDStackSets',
            Parameters=[
                {'ParameterKey': 'AdministratorAccountId', 'ParameterValue': account_id}
            ],
            Capabilities=['CAPABILITY_NAMED_IAM'],
        )
    except Exception as exc:
        print(exc)

    cleanup_stacks(
        cloudformation=boto3.client('cloudformation'),
        account_id=account_id,
        s3=boto3.resource('s3'),
        s3client=boto3.client('s3'),
        athena=boto3.client('athena'),
        glue=boto3.client('glue'),
    )

    cloudformation.delete_stack(StackName='TempDebugCIDStackSets')
    logging.info('Cleanup Done')

    # delete all log groups
    logs = boto3.client('logs')
    for log_group in logs.get_paginator('describe_log_groups').paginate(logGroupNamePrefix=f'/aws/lambda/{PREFIX}').search('logGroups'):
        logs.delete_log_group(logGroupName=log_group['logGroupName'])
        print(f"deleted {log_group['logGroupName']}")
