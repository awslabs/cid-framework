import logging
from pathlib import Path
import time

import boto3

logger = logging.getLogger(__name__)

HEADER = '\033[95m'
BLUE = '\033[94m'
CYAN = '\033[96m'
GREEN = '\033[92m'
WARNING = '\033[93m'
RED = '\033[91m'
END = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'


def clean_bucket(s3, account_id):
    try:
        bucket_name = f"costoptimizationdata{account_id}"
        logger.info(f'Emptying the bucket {GREEN}{bucket_name}{END}')
        s3.Bucket(bucket_name).object_versions.delete()
    except Exception as exc:
        logger.exception(exc)


def athena_query(athena, sql_query, sleep_duration=1, database: str=None, catalog: str='AwsDataCatalog', workgroup: str='primary'):
    """ Executes an AWS Athena Query and return dict"""
    context = {}
    if database: context['Database'] = database
    if catalog: context['Catalog'] = catalog
    response = athena.start_query_execution(
        QueryString=sql_query,
        QueryExecutionContext=context,
        WorkGroup=workgroup,
    )
    query_id = response.get('QueryExecutionId')
    current_status = athena.get_query_execution(QueryExecutionId=query_id)['QueryExecution']['Status']
    while current_status['State'] in ['SUBMITTED', 'RUNNING', 'QUEUED']:
        current_status = athena.get_query_execution(QueryExecutionId=query_id)['QueryExecution']['Status']
        time.sleep(sleep_duration)
    if current_status['State'] != "SUCCEEDED":
        failure_reason = current_status['StateChangeReason']
        logger.debug(f'Full query: {repr(sql_query)}')
        raise Exception('Athena query failed: {}'.format(failure_reason))
    results = athena.get_query_results(QueryExecutionId=query_id)
    if not results['ResultSet']['Rows']:
        return []
    keys = [r['VarCharValue'] for r in results['ResultSet']['Rows'][0]['Data']]
    return [ dict(zip(keys, [r.get('VarCharValue') for r in row['Data']])) for row in results['ResultSet']['Rows'][1:]]


def watch_stacks(cloudformation, stack_names = None):
    ''' watch stacks while they are IN_PROGRESS and/or until they are deleted'''
    if stack_names is None:
        stack_names = []
        
    last_update = {stack_name: None for stack_name in stack_names}
    while True:
        in_progress = False
        for stack_name in stack_names[:]:
            try:
                events = cloudformation.describe_stack_events(StackName=stack_name)['StackEvents']
            except cloudformation.exceptions.ClientError as exc:
                if 'does not exist' in exc.response['Error']['Message']:
                    stack_names.remove(stack_name)
            else:
                # Check events
                for e in events:
                    if not last_update.get(stack_name) or last_update.get(stack_name) < e['Timestamp']:
                        line = '\t'.join( list( dict.fromkeys([
                            e['Timestamp'].strftime("%H:%M:%S"),
                            stack_name,
                            e['LogicalResourceId'],
                            e['ResourceStatus'],
                            e.get('ResourceStatusReason',''),
                        ])))
                        if '_COMPLETE' in line: color = GREEN
                        elif '_IN_PROGRESS' in line: color = ''
                        elif '_FAILED' in line or 'failed to create' in line: color = RED
                        else: color = ''
                        logger.info(f'{color}{line}{END}')
                        last_update[stack_name] = e['Timestamp']
            try:
                current_stack = cloudformation.describe_stacks(StackName=stack_name)['Stacks'][0]
                if 'IN_PROGRESS' in current_stack['StackStatus']:
                    in_progress = True
            except:
                pass

            try:
                # Check nested stacks
                for res in cloudformation.list_stack_resources(StackName=stack_name)['StackResourceSummaries']:
                    if res['ResourceType'] == 'AWS::CloudFormation::Stack':
                        name = res['PhysicalResourceId'].split('/')[-2]
                        if name not in stack_names:
                            stack_names.append(name)
            except:
                pass

        if not stack_names or not in_progress: break
        time.sleep(5)


def initial_deploy_stacks(cloudformation, account_id, root, bucket):
    logger.info(f"account_id={account_id} region={boto3.session.Session().region_name}")
    create_options = dict(
        TimeoutInMinutes=60,
        Capabilities=['CAPABILITY_IAM','CAPABILITY_NAMED_IAM'],
        OnFailure='DELETE',
        EnableTerminationProtection=False,
        Tags=[ {'Key': 'branch', 'Value': 'branch'},],
        NotificationARNs=[],
    )
    try:
        with (root / 'Code' / 'Management.yaml').open() as fp:
            cloudformation.create_stack(
                StackName='OptimizationManagementDataRoleStack',
                TemplateBody=fp.read(),
                Parameters=[
                    {'ParameterKey': 'CostAccountID',         'ParameterValue': account_id},
                    {'ParameterKey': 'ManagementAccountRole', 'ParameterValue': "Lambda-Assume-Role-Management-Account"},
                    {'ParameterKey': 'RolePrefix',            'ParameterValue': "WA-"},
                ],
                **create_options,
            )
    except cloudformation.exceptions.AlreadyExistsException:
        logger.info('OptimizationManagementDataRoleStack exists')

    try:
        with (root / 'Code' / 'optimisation_read_only_role.yaml').open() as fp:
            cloudformation.create_stack(
                StackName='OptimizationDataRoleStack',
                TemplateBody=fp.read(),
                Parameters=[
                    {'ParameterKey': 'CostAccountID',                   'ParameterValue': account_id},
                    {'ParameterKey': 'IncludeTransitGatewayModule',     'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeBudgetsModule',            'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeECSChargebackModule',      'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeInventoryCollectorModule', 'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeRDSUtilizationModule',     'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeRightsizingModule',        'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeTAModule',                 'ParameterValue': "yes"},
                    {'ParameterKey': 'MultiAccountRoleName',            'ParameterValue': "Optimization-Data-Multi-Account-Role"},
                    {'ParameterKey': 'RolePrefix',                      'ParameterValue': "WA-"},
                ],
                **create_options,
            )
    except cloudformation.exceptions.AlreadyExistsException:
        logger.info('OptimizationDataRoleStack exists')

    try:
        with (root / 'Code' / 'Optimization_Data_Collector.yaml').open() as fp:
            cloudformation.create_stack(
                StackName="OptimizationDataCollectionStack",
                TemplateBody=fp.read(),
                Parameters=[

                    {'ParameterKey': 'CFNTemplateSourceBucket',         'ParameterValue': bucket},
                    {'ParameterKey': 'ComputeOptimizerRegions',         'ParameterValue': "us-east-1,eu-west-1"},
                    {'ParameterKey': 'DestinationBucket',               'ParameterValue': "costoptimizationdata"},
                    {'ParameterKey': 'IncludeTransitGatewayModule',     'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeBudgetsModule',            'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeComputeOptimizerModule',   'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeECSChargebackModule',      'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeInventoryCollectorModule', 'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeOrgDataModule',            'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeRDSUtilizationModule',     'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeRightsizingModule',        'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeTAModule',                 'ParameterValue': "yes"},
                    {'ParameterKey': 'ManagementAccountID',             'ParameterValue': account_id},
                    {'ParameterKey': 'ManagementAccountRole',           'ParameterValue': "Lambda-Assume-Role-Management-Account"},
                    {'ParameterKey': 'MultiAccountRoleName',            'ParameterValue': "Optimization-Data-Multi-Account-Role"},
                    {'ParameterKey': 'RolePrefix',                      'ParameterValue': "WA-"},
                ],
                **create_options,
            )
    except cloudformation.exceptions.AlreadyExistsException:
        logger.info('OptimizationDataCollectionStack exists')
        pass

    logger.info('Waiting for stacks')
    watch_stacks(cloudformation, [
        "OptimizationManagementDataRoleStack",
        "OptimizationDataRoleStack",
        "OptimizationDataCollectionStack",
    ])


def trigger_update():
    main_stack_name = 'OptimizationDataCollectionStack'
    function_names = [
        f'Accounts-Collector-Function-{main_stack_name}',
        f'pricing-Lambda-Function-{main_stack_name}',
        f'cost-explorer-rightsizing-{main_stack_name}',
        'WA-compute-optimizer-Trigger-Export',
        f'Organization-Data-{main_stack_name}',
    ]
    for name in function_names:
        logger.info('Invoking ' + name)
        response = boto3.client('lambda').invoke(FunctionName=name)
        stdout = response['Payload'].read().decode('utf-8')
        logger.info(f'Response: {stdout}')


def cleanup_stacks(cloudformation, account_id, s3, athena):
    try:
        clean_bucket(s3=s3, account_id=account_id)
    except:
        pass
    for stack_name in [
        'OptimizationManagementDataRoleStack',
        'OptimizationDataRoleStack',
        'OptimizationDataCollectionStack',
        ]:
        try:
            cloudformation.delete_stack(StackName=stack_name)
            logger.info(f'deleting {stack_name} initiated')
        except cloudformation.exceptions.ClientError as exc:
            logger.exception(stack_name)

    watch_stacks(cloudformation, [
        'OptimizationManagementDataRoleStack',
        'OptimizationDataRoleStack',
        'OptimizationDataCollectionStack',
    ])

    logger.info('Deleting all athena tables in optimization_data')
    tables = athena.list_table_metadata(CatalogName='AwsDataCatalog', DatabaseName='optimization_data')['TableMetadataList']
    for t in tables:
        logger.info('Deleting ' + t["Name"])
        athena_query(athena=athena, sql_query=f'DROP TABLE `{t["Name"]}`;', database='optimization_data')


def prepare_stacks(cloudformation, account_id, s3, bucket):
    root = Path(__file__).parent.parent
    
    initial_deploy_stacks(cloudformation=cloudformation, account_id=account_id, root=root, bucket=bucket)
    clean_bucket(s3=s3, account_id=account_id)
    trigger_update()
    logger.info('Waiting 1 min')
    time.sleep(1 * 60)
    logger.info('and another 1 min')
    time.sleep(1 * 60)