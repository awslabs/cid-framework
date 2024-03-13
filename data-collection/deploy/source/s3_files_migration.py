"""
Moving s3 objects from old structure to the new one.

Usage:
    When migrating data in the same bucket:

    python3 {prog} <ODC_bucket>

    When migrating data between 2 different buckets:

    python3 {prog} <ODC_source_bucket> <ODC_destination_bucket>

        If source and destination arguments have the same bucket name, the migration will be done in the same bucket.

"""
import re
import sys
import logging
import boto3

logger = logging.getLogger(__name__)

# Legacy/Unused objects (list of key patterns)
unused_object_key_patterns = [
    r"^organization/organization-data/payer_id=.+?ou-org.json$"
]

def migrate(bucket):
    s3 = boto3.client('s3')
    payer_id = get_payer()
    mods = {
        # Migration from v0 (no payer_id)
        "ecs-chargeback-data/year=": f"ecs-chargeback/ecs-chargeback-data/payer_id={payer_id}/year=",
        "rds_metrics/rds_stats/year=": f"rds-usage/rds-usage-data/payer_id={payer_id}/year=",
        "budgets/year=": f"budgets/budgets-data/payer_id={payer_id}/year=",
        "rightsizing/year=": f"cost-explorer-rightsizing/cost-explorer-rightsizing-data/payer_id={payer_id}/year=",
        "optics-data-collector/ami-data/year=":      f"inventory/inventory-ami-data/payer_id={payer_id}/year=",
        "optics-data-collector/ebs-data/year=":      f"inventory/inventory-ebs-data/payer_id={payer_id}/year=",
        "optics-data-collector/snapshot-data/year=": f"inventory/inventory-snapshot-data/payer_id={payer_id}/year=",
        "optics-data-collector/ta-data/year=":       f"trusted-advisor/trusted-advisor-data/payer_id={payer_id}/year=",
        "Compute_Optimizer/Compute_Optimizer_ec2_instance/year=":   f"compute_optimizer/compute_optimizer_ec2_instance/payer_id={payer_id}/year=",
        "Compute_Optimizer/Compute_Optimizer_auto_scale/year=":     f"compute_optimizer/compute_optimizer_auto_scale/payer_id={payer_id}/year=",
        "Compute_Optimizer/Compute_Optimizer_lambda/year=":         f"compute_optimizer/compute_optimizer_lambda/payer_id={payer_id}/year=",
        "Compute_Optimizer/Compute_Optimizer_ebs_volume/year=":     f"compute_optimizer/compute_optimizer_ebs_volume/payer_id={payer_id}/year=",
        "reserveinstance/year=":    f"reserveinstance/payer_id={payer_id}/year=",
        "savingsplan/year=":        f"savingsplan/payer_id={payer_id}/year=",
        "transitgateway/year=":     f"transit-gateway/transit-gateway-data/payer_id={payer_id}/year=",

        # Migration from v1 (payer_id exists)
        "ecs-chargeback-data/payer_id=": "ecs-chargeback/ecs-chargeback-data/payer_id=",
        "rds_metrics/rds_stats/payer_id=": "rds-usage/rds-usage-data/payer_id=",
        "budgets/payer_id=": "budgets/budgets-data/payer_id=",
        "rightsizing/payer_id=": "cost-explorer-rightsizing/cost-explorer-rightsizing-data/payer_id=",
        "optics-data-collector/ami-data/payer_id=":      "inventory/inventory-ami-data/payer_id=",
        "optics-data-collector/ebs-data/payer_id=":      "inventory/inventory-ebs-data/payer_id=",
        "optics-data-collector/snapshot-data/payer_id=": "inventory/inventory-snapshot-data/payer_id",
        "optics-data-collector/ta-data/payer_id=":       "trusted-advisor/trusted-advisor-data/payer_id=",
        "Compute_Optimizer/Compute_Optimizer_ec2_instance/payer_id=": "compute_optimizer/compute_optimizer_ec2_instance/payer_id=",
        "Compute_Optimizer/Compute_Optimizer_auto_scale/payer_id=":   "compute_optimizer/compute_optimizer_auto_scale/payer_id=",
        "Compute_Optimizer/Compute_Optimizer_lambda/payer_id=":       "compute_optimizer/compute_optimizer_lambda/payer_id=",
        "Compute_Optimizer/Compute_Optimizer_ebs_volume/payer_id=":   "compute_optimizer/compute_optimizer_ebs_volume/payer_id=",
        "reserveinstance/payer_id=": "reserveinstance/payer_id=",
        "savingsplan/payer_id=": "savingsplan/payer_id=",
        "transitgateway/payer_id=": "transit-gateway/transit-gateway-data/payer_id=",

        # Migration from v1.1 (adding payer to organizations)
        "organization/organization-data/([a-z\-]*?)-(\d{12}).json": rf"organization/organization-data/payer_id=\2/\1.json",

        # Migration from v2.0 to v3.0 (read roles as stack set and step functions implementation)
        "organization/organization-data/payer_id=": "organizations/organization-data/payer_id=",
        "cost-explorer-cost-anomaly/cost-anomaly-data/payer_id=": "cost-anomaly/cost-anomaly-data/payer_id=",
        "rds_usage_data/rds-usage-data/payer_id=": "rds-usage/rds-usage-data/payer_id=",
    }

    for old_prefix, new_prefix in mods.items():
        logger.debug(f'Searching for {old_prefix} in {bucket}' )
        contents =s3.list_objects_v2(Bucket=bucket, Prefix=old_prefix).get('Contents', [])
        for content in contents:
            try:
                key = content["Key"]
                if not is_unused_object(key):
                    new_key = re.sub(old_prefix, new_prefix, key)
                    logger.info(f'  Moving {key} to {new_key}')
                    copy_source = {'Bucket': bucket, 'Key': key}
                    s3.copy_object(Bucket=bucket, CopySource=copy_source, Key=new_key)
                    s3.delete_object(Bucket=bucket, Key=key)
                else:
                    logger.info(f"Removing object {key} as it is an unused object in newer versions of the data collection stack.")
                    s3.delete_object(Bucket=bucket, Key=key)
            except Exception as e:
                logger.warning(e)
    

def is_unused_object(key):
    for key_pattern in unused_object_key_patterns:
        if re.match(key_pattern, key) is not None:
            return True
        else:
            return False


def migrate_v2(source_bucket, dest_bucket):
    s3 = boto3.client("s3")
    payer_id = get_payer()
    available_mods = {
        "budgets": {
            # Migration from v0 (no payer_id)
            "budgets/year=": f"budgets/budgets-data/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists, month now double-digit)
            "budgets/payer_id=": "budgets/budgets-data/payer_id=",
            # Migration from v2.0 to v3.0 (month to double-digit)
            "month=([0-9])/": "month=0\\1/",
        },
        "optics-data-collector": {
            # Migration from v0 (no payer_id)
            "optics-data-collector/ami-data/year=": f"inventory/inventory-ami-data/payer_id={payer_id}/year=",
            "optics-data-collector/ebs-data/year=": f"inventory/inventory-ebs-data/payer_id={payer_id}/year=",
            "optics-data-collector/snapshot-data/year=": f"inventory/inventory-snapshot-data/payer_id={payer_id}/year=",
            "optics-data-collector/ta-data/year=": f"trusted-advisor/trusted-advisor-data/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "optics-data-collector/ami-data/payer_id=": "inventory/inventory-ami-data/payer_id=",
            "optics-data-collector/ebs-data/payer_id=": "inventory/inventory-ebs-data/payer_id=",
            "optics-data-collector/snapshot-data/payer_id=": "inventory/inventory-snapshot-data/payer_id",
            "optics-data-collector/ta-data/payer_id=": "trusted-advisor/trusted-advisor-data/payer_id=",
        },
        "inventory": {
            # Migration from v2.0 to v3.0 (add date partition)
            "month=([0-9]{2})/inventory-([0-9]*)-([0-9]{2})([0-9]{2})([0-9]{4})(.*)\.": "month=\\1/day=\\3/\\2-\\5-\\4-\\3.",
        },
        "ecs-chargeback-data": {
            # Migration from v0 (no payer_id)
            "ecs-chargeback-data/year=": f"ecs-chargeback/ecs-chargeback-data/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "ecs-chargeback-data/payer_id=": "ecs-chargeback/ecs-chargeback-data/payer_id=",
            # Migration from v2.0 to v3.0 (month now double-digit and add date partition)
            "month=([0-9]{1})/([0-9]*)-([0-9]{4})-([0-9]{1})-([0-9]{1})\.": "month=0\\1/day=0\\5/\\2-\\3-0\\4-0\\5.",
            "month=([0-9]{1})/([0-9]*)-([0-9]{4})-([0-9]{1})-([0-9]{2})\.": "month=0\\1/day=\\5/\\2-\\3-0\\4-\\5.",
            "month=([0-9]{2})/([0-9]*)-([0-9]{4})-([0-9]{2})-([0-9]{1})\.": "month=\\1/day=0\\5/\\2-\\3-\\4-0\\5.",
            "month=([0-9]{2})/([0-9]*)-([0-9]{4})-([0-9]{2})-([0-9]{2})\.": "month=\\1/day=\\5/\\2-\\3-\\4-\\5.",
        },
        "ecs-chargeback": {
            # Migration from v2.0 to v3.0 (month now double-digit and add date partition)
            "month=([0-9]{1})/([0-9]*)-([0-9]{4})-([0-9]{1})-([0-9]{1})\.": "month=0\\1/day=0\\5/\\2-\\3-0\\4-0\\5.",
            "month=([0-9]{1})/([0-9]*)-([0-9]{4})-([0-9]{1})-([0-9]{2})\.": "month=0\\1/day=\\5/\\2-\\3-0\\4-\\5.",
            "month=([0-9]{2})/([0-9]*)-([0-9]{4})-([0-9]{2})-([0-9]{1})\.": "month=\\1/day=0\\5/\\2-\\3-\\4-0\\5.",
            "month=([0-9]{2})/([0-9]*)-([0-9]{4})-([0-9]{2})-([0-9]{2})\.": "month=\\1/day=\\5/\\2-\\3-\\4-\\5.",
        },
        "rds_metrics": {
            # Migration from v0 (no payer_id)
            "rds_metrics/rds_stats/year=": f"rds-usage/rds-usage-data/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "rds_metrics/rds_stats/payer_id=": "rds-usage/rds-usage-data/payer_id=",
        },
        "rightsizing": {
            # Migration from v0 (no payer_id)
            "rightsizing/year=": f"cost-explorer-rightsizing/cost-explorer-rightsizing-data/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "rightsizing/payer_id=": "cost-explorer-rightsizing/cost-explorer-rightsizing-data/payer_id=",
        },
        "cost-explorer-rightsizing": {
             # Migration from v2.0 to v3.0 (month and day now double-digit)
            "month=([0-9]{1})/day=([0-9]{1})/([0-9]{4})-.*\.": "month=0\\1/day=0\\2/\\3-0\\1-0\\2.",
            "month=([0-9]{1})/day=([0-9]{2})/([0-9]{4})-.*\.": "month=0\\1/day=\\2/\\3-0\\1-\\2.",
            "month=([0-9]{2})/day=([0-9]{1})/([0-9]{4})-.*\.": "month=\\1/day=0\\2/\\3-\\1-0\\2.",
        },
        "Compute_Optimizer": {
            # Migration from v0 (no payer_id)
            "Compute_Optimizer/Compute_Optimizer_ec2_instance/year=": f"compute_optimizer/compute_optimizer_ec2_instance/payer_id={payer_id}/year=",
            "Compute_Optimizer/Compute_Optimizer_auto_scale/year=": f"compute_optimizer/compute_optimizer_auto_scale/payer_id={payer_id}/year=",
            "Compute_Optimizer/Compute_Optimizer_lambda/year=": f"compute_optimizer/compute_optimizer_lambda/payer_id={payer_id}/year=",
            "Compute_Optimizer/Compute_Optimizer_ebs_volume/year=": f"compute_optimizer/compute_optimizer_ebs_volume/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists, month now double-digit)
            "Compute_Optimizer/Compute_Optimizer_ec2_instance/payer_id=": "compute_optimizer/compute_optimizer_ec2_instance/payer_id=",
            "Compute_Optimizer/Compute_Optimizer_auto_scale/payer_id=": "compute_optimizer/compute_optimizer_auto_scale/payer_id=",
            "Compute_Optimizer/Compute_Optimizer_lambda/payer_id=": "compute_optimizer/compute_optimizer_lambda/payer_id=",
            "Compute_Optimizer/Compute_Optimizer_ebs_volume/payer_id=": "compute_optimizer/compute_optimizer_ebs_volume/payer_id=",
        },
        "reserveinstance": {
            # Migration from v0 (no payer_id)
            "reserveinstance/year=": f"reserveinstance/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "reserveinstance/payer_id=": "reserveinstance/payer_id=",
        },
        "savingsplan": {
            # Migration from v0 (no payer_id)
            "savingsplan/year=": f"savingsplan/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "savingsplan/payer_id=": "savingsplan/payer_id=",
        },
        "transitgateway": {
            # Migration from v0 (no payer_id)
            "transitgateway/year=": f"transit-gateway/transit-gateway-data/payer_id={payer_id}/year=",
            # Migration from v1 (payer_id exists)
            "transitgateway/payer_id=": "transit-gateway/transit-gateway-data/payer_id=",
        },
        "transit-gateway": {
            # Migration from v2.0 to v3.0 (month to double-digit, add date partition based on timestamp)
            "month=([0-9])/tgw-": "month=%m/day=%d/",
        },
        "organization": {
            # Migration from v1.1 (adding payer to organizations)
            "organization/organization-data/([a-z\-]*?)-(\d{12}).json": rf"organization/organization-data/payer_id=\2/\1.json",
            # Migration from v2.0 to v3.0 (prefix change)
            "organization/organization-data/payer_id=": "organizations/organization-data/payer_id=",
        },
        "cost-explorer-cost-anomaly": {
            # Migration from v2.0 to v3.0 (prefix change, force month and date partitions to double digit)
            "cost-explorer-cost-anomaly/cost-anomaly-data/payer_id=(.*)/month=([0-9])/day=([0-9])/(.{4}).*\.": "cost-anomaly/cost-anomaly-data/payer_id=\\1/month=0\\2/day=0\\3/\\4-0\\2-0\\3.",
            "cost-explorer-cost-anomaly/cost-anomaly-data/payer_id=(.*)/month=([0-9]{2})/day=([0-9])/(.{4}).*\.": "cost-anomaly/cost-anomaly-data/payer_id=\\1/month=\\2/day=0\\3/\\4-\\2-0\\3.",
            "cost-explorer-cost-anomaly/cost-anomaly-data/payer_id=(.*)/month=([0-9])/day=([0-9]{2})/(.{4}).*\.": "cost-anomaly/cost-anomaly-data/payer_id=\\1/month=0\\2/day=\\3/\\4-0\\2-\\3.",
            "cost-explorer-cost-anomaly/cost-anomaly-data/payer_id=(.*)/month=([0-9]{2})/day=([0-9]{2})/(.{4}).*\.": "cost-anomaly/cost-anomaly-data/payer_id=\\1/month=\\2/day=\\3/\\4-\\2-\\3.",
        },
        "rds_usage_data": {
            # Migration from v2.0 to v3.0 (prefix change, remove db-id partition, add day partition)
            "rds_usage_data/rds-usage-data/payer_id=(.*)/rds_id=(.*)/year=(.{4})/month=(.{2})/.{8}(.{2}).*": 
                "rds-usage/rds-usage-data/payer_id=\\1/year=\\3/month=\\4/day=\\5/\\2.json",
        },
    }

    # Apply valid mods and copy objects
    more_objects_to_fetch = True
    next_continuation_token = None

    list_objects_result = s3.list_objects_v2(
        Bucket=source_bucket,
    )

    with open("migration_log.csv", "w") as f:
        f.write(f"{source_bucket},{dest_bucket},is_modified,file_date\n")
        while more_objects_to_fetch:
            contents = list_objects_result.get("Contents", [])
            for content in contents:
                try:
                    is_mod = False
                    source_key = content["Key"]
                    if not is_unused_object(source_key):
                        file_date = content["LastModified"]
                        applicable_mods = get_applicable_mods(source_key, available_mods)
                        new_key = source_key
                        for old_prefix, new_prefix in applicable_mods.items():
                            new_prefix = file_date.strftime(new_prefix)
                            new_key = re.sub(
                                old_prefix, new_prefix, source_key
                            )  # Returns the same source_key string when no match exists for the given pattern
                            if new_key != source_key:
                                logger.info(f"Modifying source {source_key} to {new_key}")
                                is_mod = True
                                break #break the loop after the first matching pattern
                        copy_source = {"Bucket": source_bucket, "Key": source_key}
                        s3.copy_object(Bucket=dest_bucket, CopySource=copy_source, Key=new_key)
                        f.write(f"{source_key},{new_key},{is_mod},{file_date}\n")
                        logger.info(
                            f"Moving object source s3://{source_bucket}/{source_key} to s3://{dest_bucket}/{new_key}"
                        )
                        # s3.delete_object(Bucket=source_bucket, Key=source_key) # Uncomment this line if you want to delete data from the source bucket as the objects are copied
                    else:
                        if source_bucket == dest_bucket:
                            # s3.delete_object(Bucket=source_bucket, Key=key)
                            logger.info(f"Removing object {source_key} as it is an unused object in newer versions of the data collection stack, and objects are being migrated into the same source bucket.")
                        else:
                            logger.info(f"Skipping object {source_key} as it is an unused object in newer versions of the data collection stack, and objects are being migrated to a different destination bucket.")
                except Exception as e:
                    logger.warning(e)

            more_objects_to_fetch = list_objects_result["IsTruncated"]
            if more_objects_to_fetch:
                next_continuation_token = list_objects_result["NextContinuationToken"]
                list_objects_result = s3.list_objects_v2(
                    Bucket=source_bucket,
                    ContinuationToken=next_continuation_token,
                )
            else:
                next_continuation_token = None


def get_applicable_mods(object_key: str, available_mods: dict):
    top_prefix = object_key.split("/")[0]
    return available_mods.get(top_prefix, {})

def get_payer():
    org = boto3.client('organizations')
    try:
        payer_id = org.describe_organization()["Organization"]['MasterAccountId']
        logger.info(f'payer_id={payer_id}')
    except org.exceptions.AccessDeniedException:
        logger.info('Cannot read organizations. Please enter payer_id (12 digits)')
        payer_id = input('payer_id>')
        assert re.match(r'^\d{12}$', payer_id), 'Wrong user input. Payer id must be 12 digits'
    except org.exceptions.AWSOrganizationsNotInUseException:
        sts = boto3.client('sts')
        payer_id = sts.get_caller_identity()['Account']
        logger.info(f'Account is not a part of org. Using Account id = {payer_id}')
    return payer_id


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    logger.setLevel(logging.DEBUG)
    try:
        source_bucket = sys.argv[1]
        try:
            dest_bucket = sys.argv[2]
        except IndexError as exc:
            dest_bucket = source_bucket
    except:
        print(__doc__.format(prog=sys.argv[0]))
        exit(1)

    if source_bucket == dest_bucket:
        logger.info(f"Migrating files in source={source_bucket}")
        migrate(source_bucket)
    else:
        logger.info(
            f"Migrating from source={source_bucket} to destination={dest_bucket}"
        )
        migrate_v2(source_bucket, dest_bucket)