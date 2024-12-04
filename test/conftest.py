from datetime import datetime
import logging
import os


import boto3
import pytest

from utils import prepare_stacks, cleanup_stacks

logger = logging.getLogger(__name__)
_start_time = None


@pytest.fixture(scope='session')
def session():
    return boto3.session.Session()

@pytest.fixture(scope='session')
def athena():
    return boto3.client('athena')

@pytest.fixture(scope='session')
def lambda_client():
    return boto3.client('lambda')

@pytest.fixture(scope='session')
def support():
    return boto3.client('support')

@pytest.fixture(scope='session')
def cloudformation():
    return boto3.client('cloudformation')


@pytest.fixture(scope='session')
def s3():
    return boto3.resource('s3')

@pytest.fixture(scope='session')
def s3client():
    return boto3.client('s3')

@pytest.fixture(scope='session')
def compute_optimizer():
    return boto3.client('compute-optimizer')


@pytest.fixture(scope='session')
def account_id():
    return boto3.client("sts").get_caller_identity()["Account"]

@pytest.fixture(scope='session')
def org_unit_id():
    return boto3.client("organizations").list_roots()["Roots"][0]["Id"]

@pytest.fixture(scope='session')
def org_unit_id():
    return boto3.client("organizations").list_roots()["Roots"][0]["Id"]

@pytest.fixture(scope='session')
def glue():
    return boto3.client("glue")

@pytest.fixture(scope='session')
def bucket():
    bucket_name = os.environ.get('bucket')
    if bucket_name:
        return bucket_name
    print('env var `bucket` not found')
    default_bucket = f'cid-{account_id()}-test'
    s3 = boto3.client('s3')
    try:
        s3.head_bucket(Bucket=default_bucket)
        return default_bucket
    except s3.exceptions.ClientError as exc:
        print(f'bucket {default_bucket} not found in the account. {exc}')
    raise AssertionError(
        'You need a bucket to run the tests. Please set bucket env variable '
        '`export bucket=existing-bucket` or create a default bucket '
        f'`aws s3api create-bucket --bucket {default_bucket}`'
    )


@pytest.fixture(scope='session')
def start_time():
    global _start_time
    if _start_time is None:
        _start_time = datetime.now()

    return _start_time

def pytest_addoption(parser):
    parser.addoption("--mode", action="store", default="normal", choices=("normal", "no-teardown") )

@pytest.fixture(scope='session')
def mode(request):
    return request.config.getoption("--mode")

@pytest.fixture(scope='session', autouse=True)
def prepare_setup(athena, cloudformation, s3, s3client, account_id, org_unit_id, bucket, start_time, mode, glue):
    yield prepare_stacks(cloudformation=cloudformation, account_id=account_id, org_unit_id=org_unit_id, bucket=bucket, s3=s3, s3client=s3client)

    mode = pytest.params.get('mode', mode)
    if mode != "no-teardown":
        cleanup_stacks(cloudformation=cloudformation, account_id=account_id, s3=s3, s3client=s3client, athena=athena, glue=glue)