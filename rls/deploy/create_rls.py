#!/usr/bin/env python3
import boto3
import csv
from os import environ as os_environ
from sys import exit
from botocore.client import Config
import logging

CID_USER_OWNER_TAG = os_environ['CID_USER_OWNER_TAG'].strip() if 'CID_USER_OWNER_TAG' in os_environ else 'cid_users'
CID_GROUP_OWNER_TAG = os_environ['CID_GROUP_OWNER_TAG'].strip() if 'CID_GROUP_OWNER_TAG' in os_environ else 'cid_groups'
BUCKET_NAME = os_environ['BUCKET_NAME'] if 'BUCKET_NAME' in os_environ else exit(
    "Missing bucket for uploading CSV. Please define bucket as ENV VAR BUCKET_NAME")
TMP_RLS_FILE = os_environ['TMP_RLS_FILE'] if 'TMP_RLS_FILE' in os_environ else '/tmp/cid_rls.csv'
RLS_HEADER = ['UserName', 'GroupName', 'account_id', 'payer_account_id']
QS_ACCOUNT_ID = boto3.client('sts').get_caller_identity().get('Account')
QS_REGION = os_environ['QS_REGION'] if 'QS_REGION' in os_environ else exit("Missing QS_REGION var name, please define")
MANAGEMENT_ACCOUNT_IDS = os_environ['MANAGEMENT_ACCOUNT_IDS'].strip() if 'MANAGEMENT_ACCOUNT_IDS' in os_environ else QS_ACCOUNT_ID
MANAGEMENTROLENAME = os_environ['MANAGEMENTROLENAME'].strip() if 'MANAGEMENTROLENAME' in os_environ else exit(
    "Missing MANAGEMENT ROLE NAME. Please define bucket as ENV VAR MANAGEMENTROLENAME")
CID_FULL_ACCESS_USERS = os_environ['CID_FULL_ACCESS_USERS'].strip() if 'CID_FULL_ACCESS_USERS' in os_environ else None
CID_FULL_ACCESS_GROUP = os_environ['CID_FULL_ACCESS_GROUP'].strip() if 'CID_FULL_ACCESS_GROUP' in os_environ else None
RLS_LOGGING_LEVEL = os_environ['RLS_LOGGING_LEVEL'].strip() if 'RLS_LOGGING_LEVEL' in os_environ else 'INFO'


def assume_management_role(payer_id, region):
    role_name = os_environ["MANAGEMENTROLENAME"]
    partition = boto3.session.Session().get_partition_for_region(region_name=region)
    management_role_arn = f"arn:{partition}:iam::{payer_id}:role/{role_name}"
    sts_connection = boto3.client('sts')
    acct_b = sts_connection.assume_role(
        RoleArn=management_role_arn,
        RoleSessionName="cross_acct_lambda"
    )
    ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
    SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
    SESSION_TOKEN = acct_b['Credentials']['SessionToken']
    client = boto3.client(
        "organizations", region_name=region,
        aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN
    )
    return client


def update_tag_data(account, users, groups, ou_tag_data, separator=":"):
    users = users.split(separator) if users is not None else []
    groups = groups.split(separator) if groups is not None else []

    for group in groups:
        group = group.strip()

        if group in ou_tag_data['Groups']:
            if account not in ou_tag_data['Groups'][group]:
                ou_tag_data['Groups'][group]['account_id'].append(account)
        else:
            ou_tag_data['Groups'].update({group: {'account_id': [account]}})

    for user in users:
        user = user.strip()
        if user in ou_tag_data['Users']:
            if account not in ou_tag_data['Users'][user]:
                ou_tag_data['Users'][user]['account_id'].append(account)
        else:
            ou_tag_data['Users'].update({user: {'account_id': [account]}})
    return ou_tag_data


def get_children_ou(ou, org_client):
    NextToken = True
    children_ou = []
    while NextToken:
        if type(NextToken) is str:
            list_ous_result = org_client.list_organizational_units_for_parent(ParentId=ou, MaxResults=20, NextToken=NextToken)
        else:
            list_ous_result = org_client.list_organizational_units_for_parent(ParentId=ou, MaxResults=20)
        if 'NextToken' in list_ous_result:
            NextToken = list_ous_result['NextToken']
        else:
            NextToken = False
        ous = list_ous_result['OrganizationalUnits']
        for child_ou in ous:
            children_ou.append(child_ou['Id'])
    return children_ou


def get_ou_accounts(org_client, ou, accounts_list=None, process_ou_children=True):
    NextToken = True
    if accounts_list is None:
        accounts_list = []
    while NextToken:
        if type(NextToken) is str:
            list_accounts_result = org_client.list_accounts_for_parent(ParentId=ou, MaxResults=20, NextToken=NextToken)
        else:
            list_accounts_result = org_client.list_accounts_for_parent(ParentId=ou, MaxResults=20)
        if 'NextToken' in list_accounts_result:
            NextToken = list_accounts_result['NextToken']
        else:
            NextToken = False
        accounts = list_accounts_result['Accounts']
        for account in accounts:
            if account['Status'] == 'ACTIVE':
                accounts_list.append(account)
    if process_ou_children:
        for ou in get_children_ou(ou, org_client):
            get_ou_accounts(org_client, ou, accounts_list)
    return accounts_list


def dict_list_to_csv(dict):
    for key in dict:
        dict[key] = ','.join(dict[key])
    return dict


def upload_to_s3(file, s3_file):
    try:
        s3 = boto3.client('s3', os_environ["QS_REGION"], config=Config(s3={'addressing_style': 'path'}))
        s3.upload_file(file, BUCKET_NAME, f"cid_rls/{s3_file}")
    except Exception as e:
        rls_logger.debug(e)


def main(separator=":"):
    qs_rls = {'Users': {}, 'Groups': {}}
    ou_tag_data = {'Users': {}, 'Groups': {}}
    qs_client = boto3.client('quicksight', region_name=QS_REGION)
    rls_logger.debug("Fetching list of QS users")
    qs_users = get_qs_users(QS_ACCOUNT_ID, qs_client)
    qs_users = {qs_user['UserName']: qs_user['Email'] for qs_user in qs_users}
    cid_full_access_users = CID_FULL_ACCESS_USERS.split(',') if CID_FULL_ACCESS_USERS is not None else []
    rls_logger.debug(f"Global full access users: {cid_full_access_users}")
    rls_logger.debug(f"Global full access group: {CID_FULL_ACCESS_GROUP}")
    rls_logger.debug(f"Active QuickSight qs_users: {qs_users}")
    for aws_payer_acount in [r.strip() for r in MANAGEMENT_ACCOUNT_IDS.split(',')]:
        if ':' in aws_payer_acount:
            aws_payer_account_id = aws_payer_acount.split(':')[0]
            identity_region = aws_payer_acount.split(':')[1]
        else:
            aws_payer_account_id = aws_payer_acount
            identity_region = QS_REGION
        aws_org_client = assume_management_role(aws_payer_account_id, identity_region)
        root_ou = aws_org_client.list_roots()['Roots'][0]['Id']
        rls_logger.debug(f"Start processing for AWS payer account: {aws_payer_account_id}, root_ou: {root_ou}, with QS Region: {identity_region}")
        ou_tag_data = process_ou(aws_org_client, root_ou, ou_tag_data, root_ou)
        ou_tag_data = process_root_ou(aws_org_client, aws_payer_account_id, root_ou, ou_tag_data)  # -> will recreate root process
        qs_email_user_map = {}
        for key, value in qs_users.items():
            if value not in qs_email_user_map:
                qs_email_user_map[value] = [key]
            else:
                qs_email_user_map[value].append(key)
        # process all tags from all OU
        for user in ou_tag_data['Users']:
            rls_logger.debug(f"Checking if USER_EMAIL:{user} is among active QuickSight users")
            if user in qs_email_user_map:
                for qs_user in qs_email_user_map[user]:
                    if user not in cid_full_access_users:
                        rls_logger.debug(f"User: {user} is among active QuickSight users")
                        qs_rls['Users'][qs_user] = ou_tag_data['Users'][user]
                    else:
                        rls_logger.debug(f"User: {user} is a full access active QuickSight users")
                        qs_rls['Users'][qs_user] = {'full_access': True}
    qs_rls['Groups'] = ou_tag_data['Groups']
    rls_logger.debug(f"List of Active QuickSight users: {qs_email_user_map}")
    rls_logger.debug(f"Dictionary with QuickSight  RLS DATA: {qs_rls}")
    rls_s3_filename = "cid_rls.csv"
    write_csv(qs_rls, rls_s3_filename)


def get_qs_users(account_id, qs_client):
    rls_logger.debug("Fetching Active QuickSight users, Getting first page, NextToken: 0")
    qs_users_result = (qs_client.list_users(AwsAccountId=account_id, MaxResults=100, Namespace='default'))
    qs_users = qs_users_result['UserList']

    while 'NextToken' in qs_users_result:
        NextToken = qs_users_result['NextToken']
        qs_users_result = (qs_client.list_users(AwsAccountId=account_id, MaxResults=100, Namespace='default', NextToken=NextToken))
        qs_users.extend(qs_users_result['UserList'])
        rls_logger.debug("Fetching QuickSight users, getting Next Page, NextToken: {}".format(NextToken.split('/')[0]))

    for qs_users_index, qs_user in enumerate(qs_users):
        qs_user = {'UserName': qs_user['UserName'], 'Email': qs_user['Email']}
        qs_users[qs_users_index] = qs_user

    return qs_users


def process_account(account_id, ou_tag_data, ou, org_client):
    rls_logger.debug(f"proessing account level tags, processing account_id: {account_id}")
    tags = org_client.list_tags_for_resource(ResourceId=account_id)['Tags']
    for tag in tags:
        rls_logger.debug(f"processing child account: {account_id} for ou: {ou}")
        if tag['Key'] == CID_USER_OWNER_TAG:
            cid_users_tag_value = tag['Value']
            ou_tag_data = update_tag_data(account_id, cid_users_tag_value, None, ou_tag_data)
        elif tag['Key'] == CID_GROUP_OWNER_TAG:
            cid_groups_tag_value = tag['Value']
            ou_tag_data = update_tag_data(account_id, None, cid_groups_tag_value, ou_tag_data)
    return ou_tag_data


def process_root_ou(org_client, payer_id, root_ou, ou_tag_data):
    "PROCESS OU MUST BE PROCESSED LAST"
    tags = org_client.list_tags_for_resource(ResourceId=root_ou)['Tags']
    for tag in tags:
        if tag['Key'] == CID_USER_OWNER_TAG:
            cid_users_tag_value = tag['Value']
            for user in cid_users_tag_value.split(':'):
                if user in ou_tag_data['Users']:
                    if 'payer_id' in ou_tag_data['Users'][user]:
                        if payer_id not in ou_tag_data['Users'][user]['payer_id']:
                            ou_tag_data['Users'][user]['payer_id'].append(payer_id)
                    else:
                        ou_tag_data['Users'][user]['payer_id'] = [payer_id]
                else:
                    ou_tag_data['Users'].update({user: {'payer_id': [payer_id]}})

        if tag['Key'] == CID_GROUP_OWNER_TAG:
            cid_groups_tag_value = tag['Value']
            for group in cid_groups_tag_value.split(':'):
                if group in ou_tag_data['Groups']:
                    if 'payer_id' in ou_tag_data['Groups'][group]:
                        if payer_id not in ou_tag_data['Groups'][group]['payer_id']:
                            ou_tag_data['Groups'][group]['payer_id'].append(payer_id)
                    else:
                        ou_tag_data['Groups'][group]['payer_id'] = [payer_id]
                else:
                    ou_tag_data['Groups'].update({group: {'payer_id': [payer_id]}})
    return ou_tag_data


def process_ou(org_client, ou, ou_tag_data, root_ou):
    rls_logger.debug(f"Start processing ou {ou}, for root ou: {root_ou}")
    tags = org_client.list_tags_for_resource(ResourceId=ou)['Tags']
    rls_logger.debug(f"Adding tags to all subacounts of  {ou}, for root ou: {root_ou}")
    for tag in tags:
        if tag['Key'] == CID_GROUP_OWNER_TAG:  # ADD GROUP TAGS
            cid_groups_tag_value = tag['Value']
            """ Do not process all children if this is root ou, for ROOT_OU we have a separate function, this is done bellow in separate cycle. """
            process_ou_children = bool(ou != root_ou)
            user_ou_accounts = get_ou_accounts(org_client, ou, process_ou_children=process_ou_children)
            for account in user_ou_accounts:
                account_id = account['Id']
                rls_logger.debug(f"Adding inherit USER tag: {cid_groups_tag_value} for ou: {ou} to account_id: {account_id}")
                ou_tag_data = update_tag_data(account_id, None, cid_groups_tag_value, ou_tag_data)

        if tag['Key'] == CID_USER_OWNER_TAG:  # ADD USER TAGS
            cid_users_tag_value = tag['Value']
            """ Do not process all children if this is root ou, for ROOT_OU we have a separate function, this is done bellow in separate cycle. """
            process_ou_children = bool(ou != root_ou)
            group_ou_accounts = get_ou_accounts(org_client, ou, process_ou_children=process_ou_children)
            for account in group_ou_accounts:
                account_id = account['Id']
                rls_logger.debug(f"Adding inherit GROUP tag: {cid_users_tag_value} for ou: {ou} to account_id: {account_id}")
                ou_tag_data = update_tag_data(account_id, cid_users_tag_value, None, ou_tag_data)

    children_ou = get_children_ou(ou, org_client)
    if len(children_ou) > 0:
        rls_logger.debug(f"Itterating other OUS: {children_ou} for parrent ou: {ou}")
        for child_ou in children_ou:
            rls_logger.debug(f"Processing child ou: {child_ou}, parent ou: {ou}, root ou: {root_ou}")
            ou_tag_data = process_ou(org_client, child_ou, ou_tag_data, root_ou)
    else:
        rls_logger.debug(f"got 0 children OUS for parent ou: {ou}")

    ou_accounts = get_ou_accounts(org_client, ou, process_ou_children=False)  # Do not process children, only accounts at OU level.
    ou_accounts_ids = [ou_account['Id'] for ou_account in ou_accounts]
    rls_logger.debug(f"Getting accounts in  OU: {ou} ########################### ou_accounts:{ou_accounts_ids}")
    for account in ou_accounts:
        account_id = account['Id']
        rls_logger.debug(f"Getting tags for account: {account_id} of ou: {ou}")
        ou_tag_data = process_account(account_id, ou_tag_data, ou, org_client)
    return ou_tag_data


def write_csv(qs_rls, rls_s3_filename):
    with open(TMP_RLS_FILE, 'w', newline='') as cid_rls_csv_file:
        wrt = csv.DictWriter(cid_rls_csv_file, fieldnames=RLS_HEADER)
        wrt.writeheader()
        """ First row add QS Full access Group """
        if CID_FULL_ACCESS_GROUP is not None:
            wrt.writerow({'UserName': "",
                          'GroupName': CID_FULL_ACCESS_GROUP,
                          'account_id': "",
                          'payer_account_id': ""})
        for group in qs_rls['Groups']:
            """ we will write empty account_id, if payer_id is present, cause the user should see all accounts under one payer
                and we will write empty payer_id if payer_id is absent """
            if 'payer_id' in qs_rls['Groups'][group]:
                wrt.writerow({'UserName': "",
                              'GroupName': group,
                              'account_id': "",
                              'payer_account_id': ",".join(qs_rls['Groups'][group]['payer_id'])})
            elif qs_rls['Groups'][group].get('full_access'):
                wrt.writerow({'UserName': "",
                              'GroupName': group,
                              'account_id': "",
                              'payer_account_id': ""})
            else:
                wrt.writerow({'UserName': "",
                              'GroupName': group,
                              'account_id': ",".join(qs_rls['Groups'][group]['account_id']),
                              'payer_account_id': ""})

        for user in qs_rls['Users']:
            """ we will write empty account_id, if payer_id is present, cause the user should see all accounts under one payer
                and we will write empty payer_id if payer_id is absent """
            if 'payer_id' in qs_rls['Users'][user]:
                wrt.writerow({'UserName': user,
                              'GroupName': "",
                              'account_id': "",
                              'payer_account_id': ",".join(qs_rls['Users'][user]['payer_id'])})
            elif qs_rls['Users'][user].get('full_access'):
                wrt.writerow({'UserName': user,
                              'GroupName': "",
                              'account_id': "",
                              'payer_account_id': ""})
            else:
                wrt.writerow({'UserName': user,
                              'GroupName': "",
                              'account_id': ",".join(qs_rls['Users'][user]['account_id']),
                              'payer_account_id': ""})

    upload_to_s3(TMP_RLS_FILE, rls_s3_filename)


def set_log_level(RLS_LOGGING_LEVEL):
    logging_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    if RLS_LOGGING_LEVEL in logging_levels.keys():
        RLS_LOGGING_LEVEL = logging_levels[RLS_LOGGING_LEVEL]
    else:
        RLS_LOGGING_LEVEL = logging.INFO

    rls_logger = logging.getLogger('rls_logger')
    rls_log_handler = logging.StreamHandler()
    rls_formater = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    rls_logger.setLevel(level=RLS_LOGGING_LEVEL)
    rls_log_handler.setLevel(level=RLS_LOGGING_LEVEL)

    rls_log_handler.setFormatter(rls_formater)
    rls_logger.addHandler(rls_log_handler)
    return rls_logger


def lambda_handler(event, context):
    main()


rls_logger = set_log_level(RLS_LOGGING_LEVEL)
if __name__ == '__main__':
    main()
