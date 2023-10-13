## CID Data Collection

### About

This projects demonstrates usage of AWS API for collecting various types of usage data.

### Architecture

![Architecture](/data-collection/images/archi.png)

1. Amazon EventBridge rule invokes Step Function of every every deployed data collection module. based on schedule.
2. The Step Function launches a Lambda function Account Collector that assumes Read Role role in the Management account and retrieves linked accounts list via AWS Organizations API
3. Step Functions launches Data Collection Lambda function for each collected Account.
4. Each data collection module Lambda function assumes IAM role in linked accounts and retrieves respective optimization data via AWS SDK for Python. Retrieved data aggregated in Amazon S3 bucket
5. Once data stored in S3 bucket, Step Functions triggers AWS Glue crawler which creates or updates the table in Glue Data Catalog
6. Collected data visualized with the Cloud Intelligence Dashboards using Amazon QuickSight to get optimization recommendations and insights


### Modules
List of modules and objects collected:
| Module Name                  | AWS Services          | Collected In        | Details  |
| ---                          |  ---                  | ---                 | ---      |
| `organization`               | AWS Organizations     | Management Account  |          |
| `budgets`                    | AWS Budgest           | Linked Account      |          |
| `compute-optimizer`          | AWS Compute Optimizer | Management Account  |          |
| `trusted-advisor`            | AWS Trusted Advisor   | Linked Account      |          |
| `cost-explorer-cost-anomaly` | AWS Anomalies         | Management Account  |          |
| `cost-explorer-rightsizing`  | AWS Cost Explorer     | Management Account  |          |
| `inventory`                  | Various services      | Linked Account      | `Opensearch Domains`, `Elasticache Clusters`, `RDS DB Instances`, `EBS Volumes`, `AMI`, `EBS Snapshot` |
| `pricing`                    | Various services      | N/A                 | `Amazon RDS`, `Amazon EC2`, `Amazon ElastiCache`, `Amazon Opensearch`, `AWS Compute Savings Plan` |
| `rds-usage`                  |  Amazon RDS           | Linked Account      | Collects CloudWatch metrics |
| `transit-gateway`            |  AWS Transit Gateway  | Linked Account      | Collects CloudWatch metrics for chargeback |
| `ecs-chargeback`             |  Amazon ECS           | Linked Account      |  |



### Installation

#### In Management Account(s)
1. Install the Stack with a read role:
   * [Launch Stack](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?&templateURL=https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/data-collection/deploy-in-management-account.yaml&stackName=CidDataCollectionManagementAccountRole&param_DataCollectionAccountID=REPLACE%20WITH%20DATA%20COLLECTION%20ACCOUNT%20ID&param_IncludeTAModule=yes&param_IncludeRightsizingModule=no&param_IncludeCostAnomalyModule=yes&param_IncludeInventoryCollectorModule=yes&param_IncludeComputeOptimizerModule=yes&param_IncludeECSChargebackModule=no&param_IncludeRDSUtilizationModule=no&param_IncludeOrgDataModule=yes&param_IncludeBudgetsModule=yes&param_IncludeTransitGatewayModule=no)

2. Deploy StackSet
   * Go to [StackSet Create Page](https://console.aws.amazon.com/cloudformation/home#/stacksets/create)
   * Specify templateUrl `https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/data-collection/deploy-in-linked-account.yaml` you can use buckets deployed in other regions as well.

3. Deploy Account Read Stack (optional)
   * [Launch Stack](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?&templateURL=https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/data-collection/deploy-in-linked-account.yaml&stackName=CidDataCollectionManagementAccountRole&param_DataCollectionAccountID=REPLACE%20WITH%20DATA%20COLLECTION%20ACCOUNT%20ID&param_IncludeTAModule=yes&param_IncludeRightsizingModule=no&param_IncludeCostAnomalyModule=yes&param_IncludeInventoryCollectorModule=yes&param_IncludeComputeOptimizerModule=yes&param_IncludeECSChargebackModule=no&param_IncludeRDSUtilizationModule=no&param_IncludeOrgDataModule=yes&param_IncludeBudgetsModule=yes&param_IncludeTransitGatewayModule=no)


#### In Data Collection Account

1. Deploy Data Collection Stack

   * [Launch Stack](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?&templateURL=https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/data-collection/deploy-data-collection.yaml&stackName=CidDataCollectionStack&param_ManagementAccountID=REPLACE%20WITH%20MANAGEMENT%20ACCOUNT%20ID&param_IncludeTAModule=yes&param_IncludeRightsizingModule=no&param_IncludeCostAnomalyModule=yes&param_IncludeInventoryCollectorModule=yes&param_IncludeComputeOptimizerModule=yes&param_IncludeECSChargebackModule=no&param_IncludeRDSUtilizationModule=no&param_IncludeOrgDataModule=yes&param_IncludeBudgetsModule=yes&param_IncludeTransitGatewayModule=no)

#### Usage
Check Athena tables.

### FAQ
#### Migration from previous Data Collection Lab


