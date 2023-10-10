# CONTRIBUTION GUIDE

# Development process

## Testing environment
You can test this lab in a dedicated account that preferably has the following assets:
* EC2 instances, running more than 14 days (for Compute Optimizer and CE Rightsizing)
* At least one EBS and one volume Snapshot
* At least one custom AMI created from one of the snapshots
* Activated Enterprise Support (for TA module)
* An RDS cluster or single instance
* An ECS cluster with one service deployed ([wordpress](https://aws.amazon.com/blogs/containers/running-wordpress-amazon-ecs-fargate-ecs/) will work fine)
* A TransitGateway with at least one attachment
* AWS Organization
* An S3 bucket to store the CloudFormation templates that deploy the infrastructure for the optimization data collection components

## Prerequisites for local environment

### General

* [cfn_nag_scan](https://github.com/stelligent/cfn_nag#installation)
* python3.8+
* `pip3 install -U boto3 pytest cfn-flip pylint checkov`
* Configured AWS credentials

## Testing

### AWS access credentials

For the purpose of testing, Python and shell scripts will make use of default AWS credentials setup in your ~/.aws folder.

Make sure you configure credentials for an organizations management account that will have the necessary permission to retrieve information from itself and other member accounts.

`aws configure` can be used to setup the AWS credentials in your local environment.

### Steps

1. (One time) Clone the project locally and install dependencies

```bash
git clone git@github.com:awslabs/cid-framework.git
cd cid-framework
pip3 install -U boto3 pytest cfn-flip pylint cfn-lint checkov
```

Create a test bucket in test account. You can use any bucket.

```bash
export account_id=$(aws sts get-caller-identity --query "Account" --output text )
export bucket=cid-$account_id-test

aws s3api create-bucket --bucket $bucket
```

2. Check the quality of code:

Cloud Formation:
```bash
./Data_Collection/Optimization/Tools/lint.sh
```

Pylint:
```bash
python3 ./Data_Collection/Optimization/Tools/pylint.py
```


3. Upload the code to a bucket and run integration tests in your testing environment

```bash
export account_id=$(aws sts get-caller-identity --query "Account" --output text )
export bucket=cid-$account_id-test
./Data_Collection/Optimization/Tools/upload.sh  "$bucket"
python3 ./Data_Collection/Optimization/Test/test_from_scratch.py
```

The test will install stacks from scratch in a single account, then it will check the presence of Athena tables. After running tests, it will delete the stacks and all artefacts that are not deleted by CFN.

# Release process
All yaml and zip files are in the account 87******** - well-architected-content@amazon.com, in the bucket `aws-well-architected-labs`. These are then replicated to the other regional buckets.

```bash
./Data_Collection/Optimization/Tools/upload.sh  "aws-well-architected-labs"
```


## Adding more buckets
Each region requires a bucket for lambda code. To add a regional bucket follow these steps:
* create bucket following the naming convention aws-well-architected-labs-<region>
* 'Block all public access' Set to > Off
* Access control list (ACL) Change from default to  ACLs enabled
* add this to the role s3-replication-role
* Add bucket policy below
* create a replication role on the aws-well-architected-labs bucket on prefix Cost/Labs/300_Optimization_Data_Collection/
* Use the s3-replication-role role
* Select replicate existing files
* New files will be replicated

```json
    {
        "Version": "2008-10-17",
        "Id": "PolicyForCloudFrontPrivateContent",
        "Statement": [
            {
                "Sid": "1",
                "Effect": "Allow",
                "Principal": {
                    "AWS": "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity E3RRAWK7UHVS3O"
                },
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::aws-well-architected-labs-[bucket location]/*"
            }
        ]
    }
```
