
import json
import time
import logging
from pathlib import Path
from datetime import datetime

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
        logger.info(f'Emptying the bucket {CYAN}{bucket_name}{END}')
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


def deploy_stack(cloudformation, stack_name: str, file: Path, parameters: list[dict]):
    create_options = dict(
        TimeoutInMinutes=60,
        Capabilities=['CAPABILITY_IAM','CAPABILITY_NAMED_IAM'],
        OnFailure='DELETE',
        EnableTerminationProtection=False,
        Tags=[ {'Key': 'branch', 'Value': 'branch'},],
        NotificationARNs=[],
    )

    try:
        with file.open() as fp:
            cloudformation.create_stack(
                StackName=stack_name,
                TemplateBody=fp.read(),
                Parameters=parameters,
                **create_options,
            )
    except cloudformation.exceptions.AlreadyExistsException:
        logger.info(f'{stack_name} exists')

def initial_deploy_stacks(cloudformation, account_id, root, bucket):
    logger.info(f"account_id={account_id} region={boto3.session.Session().region_name}")

    deploy_stack(cloudformation=cloudformation,
                    stack_name='OptimizationManagementDataRoleStack',
                    file=root / 'Code' / 'Management.yaml',
                    parameters=[
                        {'ParameterKey': 'CostAccountID',         'ParameterValue': account_id},
                        {'ParameterKey': 'ManagementAccountRole', 'ParameterValue': "Lambda-Assume-Role-Management-Account"},
                        {'ParameterKey': 'RolePrefix',            'ParameterValue': "WA-"},
                    ]
    )

    deploy_stack(cloudformation=cloudformation,
                 stack_name='OptimizationDataRoleStack',
                 file=root / 'Code' / 'optimisation_read_only_role.yaml',
                 parameters=[
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
                 ]
    )

    deploy_stack(cloudformation=cloudformation,
                 stack_name='OptimizationDataCollectionStack',
                 file=root / 'Code' / 'Optimization_Data_Collector.yaml',
                 parameters=[
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
                    {'ParameterKey': 'IncludeCostAnomalyModule',        'ParameterValue': "yes"},
                    {'ParameterKey': 'IncludeTAModule',                 'ParameterValue': "yes"},
                    {'ParameterKey': 'ManagementAccountID',             'ParameterValue': account_id},
                    {'ParameterKey': 'ManagementAccountRole',           'ParameterValue': "Lambda-Assume-Role-Management-Account"},
                    {'ParameterKey': 'MultiAccountRoleName',            'ParameterValue': "Optimization-Data-Multi-Account-Role"},
                    {'ParameterKey': 'RolePrefix',                      'ParameterValue': "WA-"},
                 ]
    )

    logger.info('Waiting for stacks')
    watch_stacks(cloudformation, [
        "OptimizationManagementDataRoleStack",
        "OptimizationDataRoleStack",
        "OptimizationDataCollectionStack",
    ])


def launch_(state_machine_arns, lambda_arns=None, wait=True):
    stepfunctions = boto3.client('stepfunctions')
    logs_client = boto3.client('logs')

    # Execute lambdas
    lambda_arns = set(lambda_arns or [])
    for lambda_arn in lambda_arns:
        boto3.client('lambda').invoke(
            FunctionName=lambda_arn.split(':')[-1],
            InvocationType='Event', # Async
        )

    # Execute sate machines
    execution_arns = []
    for state_machine_arn in state_machine_arns:
        executions = stepfunctions.list_executions(
            stateMachineArn=state_machine_arn,
        )['executions']
        logger.info(f'{state_machine_arn} has : {executions}')

        executions = stepfunctions.list_executions(
            stateMachineArn=state_machine_arn,
            statusFilter='RUNNING'  # Filter for running executions
        )['executions']
        if executions:
            logger.info(f'{state_machine_arn} has already started: {executions}')
            continue

        execution_arn = stepfunctions.start_execution(stateMachineArn=state_machine_arn)['executionArn']
        logger.info(f'Starting {execution_arn}')
        execution_arns.append(execution_arn)

        # Extract Lambda function ARNs from the state machine definition
        state_machine_definition = json.loads(stepfunctions.describe_state_machine(stateMachineArn=state_machine_arn)['definition'])
        def _extract_lambda_arns(state):
            if str(state).startswith('arn:aws:lambda:'):
                lambda_arns.add(state)
            elif isinstance(state, dict):
                for value in state.values():
                    _extract_lambda_arns(value)
            elif isinstance(state, list):
                for item in state:
                    _extract_lambda_arns(item)
        _extract_lambda_arns(state_machine_definition)

    if not wait:
        return

    # Wait for state machines to complete
    last_log_time = {lambda_arn: int(time.time()) * 1000 for lambda_arn in lambda_arns}
    execution_results = {execution_arn: None for execution_arn in execution_arns}
    running = True
    while running:
        # check if there are still running
        running = False
        for execution_arn in execution_arns:
            res = stepfunctions.describe_execution(executionArn=execution_arn)
            if res['status'] == 'RUNNING':
                running = True
            else:
                if not execution_results[execution_arn]:
                    execution_results[execution_arn] = res['status']
                    print(res['executionArn'], res['status'])
        # read logs of all lambdas
        for lambda_arn in lambda_arns:
            function_name = lambda_arn.split(':')[-1]
            log_groups = logs_client.describe_log_groups(logGroupNamePrefix='/aws/lambda/' + function_name)
            for log_group in log_groups['logGroups']:
                events = logs_client.filter_log_events(
                    logGroupName=log_group['logGroupName'],
                    startTime=last_log_time[lambda_arn]
                )['events']
                if events:
                    last_log_time[lambda_arn] = events[-1]['timestamp'] + 1
                for event in events:
                    if 'error' in event['message'].lower() or 'exception' in event['message'].lower():
                        print(event['timestamp'])
                        print(
                            datetime.utcfromtimestamp(event['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S') + ' ' +
                            function_name  + ': ' +
                            event['message'][:-1]
                        )
    # Show results
    for arn, res in execution_results.items():
        print(arn, res)


def trigger_update(account_id):
    region = boto3.session.Session().region_name
    state_machine_arns = [
       # f'arn:aws:states:{region}:{account_id}:stateMachine:WA-budgets-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-ecs-chargeback-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-rds_usage_data-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-transit-gateway-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-trusted-advisor-StateMachine',
    ]
    lambda_arns = [
        f"arn:aws:lambda:{region}:{account_id}:function:WA-compute-optimizer-Lambda-Trigger-Export",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-cost-explorer-cost-anomaly-Lambda-Collect",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-cost-explorer-rightsizing-Lambda-Collect",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-organization-Lambda-Collect",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-pricing-Lambda-Collect-EC2Pricing",
        #f"arn:aws:lambda:{region}:{account_id}:function:WA-pricing-Lambda-Collect-RDS",
    ]
    launch_(state_machine_arns, lambda_arns, wait=True)


def cleanup_stacks(cloudformation, account_id, s3, athena):
    try:
        clean_bucket(s3=s3, account_id=account_id)
    except Exception as ex:
        logger.warning(f'Exception: {ex}')

    for stack_name in [
        'OptimizationManagementDataRoleStack',
        'OptimizationDataRoleStack',
        'OptimizationDataCollectionStack',
        ]:
        try:
            cloudformation.delete_stack(StackName=stack_name)
            logger.info(f'deleting {stack_name} initiated')
        except cloudformation.exceptions.ClientError as exc:
            logger.error(f'{stack_name} {exc}')

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
    trigger_update(account_id=account_id)
    logger.info('Waiting 1 min')
    time.sleep(1 * 60)