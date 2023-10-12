
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

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


def clean_bucket(s3, s3client, account_id, full=True):
    try:
        bucket_name = f"costoptimizationdata{account_id}"

        if full:
            # Delete all
            logger.info(f'Emptying the bucket {CYAN}{bucket_name}{END}')
            s3.Bucket(bucket_name).object_versions.delete()
        else:
            # Delete all objects older than 5 mins
            now = datetime.utcnow().replace(tzinfo=timezone(timedelta()))
            objects = s3client.list_objects_v2(Bucket=bucket_name)['Contents']
            if objects:
                logger.info(f'Removing old objects the bucket {CYAN}{bucket_name}{END}')
            for obj in objects:
                age_mins =  (now-obj['LastModified']).total_seconds() / 60
                if age_mins > 5:
                    logger.info(f"{age_mins} mins old. deleting {obj['Key']}")
                    s3client.delete_object(Bucket=bucket_name, Key=obj['Key'])
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
                for res in cloudformation.s3clients(StackName=stack_name)['StackResourceSummaries']:
                    if res['ResourceType'] == 'AWS::CloudFormation::Stack':
                        name = res['PhysicalResourceId'].split('/')[-2]
                        if name not in stack_names:
                            stack_names.append(name)
            except:
                pass

        if not stack_names or not in_progress: break
        time.sleep(5)


def deploy_stack(cloudformation, stack_name: str, file: Path, parameters: list[dict]):

    options = dict(
        StackName=stack_name,
        Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM', 'CAPABILITY_AUTO_EXPAND'],
        Tags=[ {'Key': 'branch', 'Value': 'branch'},],
        NotificationARNs=[],
        TemplateBody=file.open().read(),
        Parameters=parameters,
    )

    try:
        cloudformation.create_stack(
            EnableTerminationProtection=False,
            OnFailure='DELETE',
            TimeoutInMinutes=60,
            **options,
        )
    except cloudformation.exceptions.AlreadyExistsException:
        try:
            logger.info(f'{stack_name} exists')
            cloudformation.update_stack(
                **options,
            )
        except cloudformation.exceptions.ClientError as exc:
            if 'No updates are to be performed.' in str(exc):
                logger.info(f'No updates are to be performed for {stack_name}')
            else:
                logger.error(exc)


def initial_deploy_stacks(cloudformation, account_id, root, bucket):
    logger.info(f"account_id={account_id} region={boto3.session.Session().region_name}")

    deploy_stack(
        cloudformation=cloudformation,
        stack_name='OptimizationManagementDataRoleStack',
        file=root / 'deploy' / 'deploy-in-management-account.yaml',
        parameters=[
            {'ParameterKey': 'DataCollectionAccountID', 'ParameterValue': account_id},
            {'ParameterKey': 'ManagementAccountRole',   'ParameterValue': "Lambda-Assume-Role-Management-Account"},
            {'ParameterKey': 'RolePrefix',              'ParameterValue': "WA-"},
        ]
    )

    deploy_stack(
        cloudformation=cloudformation,
        stack_name='OptimizationDataRoleStack',
        file=root / 'deploy' / 'deploy-in-linked-account.yaml',
        parameters=[
            {'ParameterKey': 'DataCollectionAccountID',         'ParameterValue': account_id},
            {'ParameterKey': 'IncludeTransitGatewayModule',     'ParameterValue': "yes"},
            {'ParameterKey': 'IncludeBudgetsModule',            'ParameterValue': "yes"},
            {'ParameterKey': 'IncludeECSChargebackModule',      'ParameterValue': "yes"},
            {'ParameterKey': 'IncludeInventoryCollectorModule', 'ParameterValue': "yes"},
            {'ParameterKey': 'IncludeRDSUtilizationModule',     'ParameterValue': "yes"},
            {'ParameterKey': 'IncludeTAModule',                 'ParameterValue': "yes"},
            {'ParameterKey': 'MultiAccountRoleName',            'ParameterValue': "Optimization-Data-Multi-Account-Role"},
            {'ParameterKey': 'RolePrefix',                      'ParameterValue': "WA-"},
        ]
    )

    deploy_stack(
        cloudformation=cloudformation,
        stack_name='OptimizationDataCollectionStack',
        file=root / 'deploy' / 'deploy-data-collection.yaml',
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


def launch_(state_machine_arns, lambda_arns=None, lambda_norun_arns=None, wait=True):
    stepfunctions = boto3.client('stepfunctions')
    logs_client = boto3.client('logs')
    started = datetime.now().astimezone()

    # Execute lambdas
    lambda_arns = lambda_arns or []
    for lambda_arn in lambda_arns:
        boto3.client('lambda').invoke(
            FunctionName=lambda_arn.split(':')[-1],
            InvocationType='Event', # Async
        )
    lambda_arns = set((lambda_norun_arns or []) + (lambda_arns or []))


    # Execute sate machines
    execution_arns = []

    for state_machine_arn in state_machine_arns:
        executions = stepfunctions.list_executions(
            stateMachineArn=state_machine_arn,
        )['executions']
        for execution in executions:
            if execution['status'] == 'RUNNING':
                execution_arns.append(execution['executionArn'])
            if (started - execution['startDate']).total_seconds() < 1 * 60:
                logger.info(f"Already started {execution['executionArn']}")
                break # no need to start execution if there is a recent one
        else:
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
        # check if there are running stepfunctions
        running = False
        for execution_arn in execution_arns:
            res = stepfunctions.describe_execution(executionArn=execution_arn)
            if res['status'] == 'RUNNING':
                running = True
            else:
                if not execution_results[execution_arn]:
                    execution_results[execution_arn] = res['status']
                    if res['status'].upper() in ['FAILED']:
                        logger.warning(f"{execution_arn} {res['status']}")
                    else:
                        logger.info(f"{execution_arn} {res['status']}")
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
                        logger.warning(
                            datetime.utcfromtimestamp(event['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S') + ' ' +
                            function_name  + ': ' +
                            event['message'][:-1]
                        )
    # Show results
    for arn, res in execution_results.items():
        if str(res).upper() in ['FAILED']:
            logger.warning(f'{arn} {res}')
        else:
            logger.info(f'{arn} {res}')



def trigger_update(account_id):
    region = boto3.session.Session().region_name
    state_machine_arns = [
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-budgets-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-ecs-chargeback-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-OpensearchDomains-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-ElasticacheClusters-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-RdsDbInstances-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-EBS-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-AMI-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-inventory-Snapshot-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-rds-usage-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-transit-gateway-StateMachine',
        f'arn:aws:states:{region}:{account_id}:stateMachine:WA-trusted-advisor-StateMachine',
    ]
    lambda_arns = [
        f"arn:aws:lambda:{region}:{account_id}:function:WA-compute-optimizer-Lambda-Trigger-Export",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-cost-explorer-cost-anomaly-Lambda-Collect",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-cost-explorer-rightsizing-Lambda-Collect",
        f"arn:aws:lambda:{region}:{account_id}:function:WA-organization-Lambda-Collect",
    ]
    lambda_norun_arns = [
        f"arn:aws:lambda:{region}:{account_id}:function:WA-pricing-Lambda-Collect-Pricing",
    ]
    launch_(state_machine_arns, lambda_arns, lambda_norun_arns, wait=True)


def cleanup_stacks(cloudformation, account_id, s3, s3client, athena, glue):

    for index in range(10):
        print(f'Press Ctrl+C if you want to avoid teardown: {9-index}\a') # beep
        time.sleep(1)

    try:
        clean_bucket(s3=s3, s3client=s3client, account_id=account_id)
    except Exception as exc:
        logger.warning(f'Exception: {exc}')

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
    try:
        logger.info('Deleting all athena tables in optimization_data')
        tables = athena.list_table_metadata(CatalogName='AwsDataCatalog', DatabaseName='optimization_data')['TableMetadataList']
        for table in tables:
            logger.info('Deleting ' + table["Name"])
            athena_query(athena=athena, sql_query=f'DROP TABLE `{table["Name"]}`;', database='optimization_data')
    except Exception:
        pass

    try:
        glue.delete_database(CatalogId='AwsDataCatalog', Name='optimization_data')
    except Exception:
        pass

def prepare_stacks(cloudformation, account_id, s3, s3client, bucket):
    root = Path(__file__).parent.parent
    initial_deploy_stacks(cloudformation=cloudformation, account_id=account_id, root=root, bucket=bucket)
    clean_bucket(s3=s3, s3client=s3client,  account_id=account_id, full=False)
    trigger_update(account_id=account_id)
