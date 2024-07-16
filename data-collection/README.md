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
| `compute-optimizer`          | AWS Compute Optimizer | Management Account  | Requires [Enablement of Compute Optimizer](https://aws.amazon.com/compute-optimizer/getting-started/#:~:text=Opt%20in%20for%20Compute%20Optimizer,created%20automatically%20in%20your%20account.) |
| `trusted-advisor`            | AWS Trusted Advisor   | Linked Account      | Requires Enterpriso or OnRamp Support Level |
| `cost-explorer-cost-anomaly` | AWS Anomalies         | Management Account  |          |
| `cost-explorer-rightsizing`  | AWS Cost Explorer     | Management Account  | DEPRECATED. Please use `cost-optimization-hub` |
| `inventory`                  | Various services      | Linked Account      | Collects `Amazon OpenSearch Domains`, `Amazon ElastiCache Clusters`, `RDS DB Instances`, `EBS Volumes`, `AMI`, `EC2 Instances`, `EBS Snapshot`, `RDS Snapshot`, `Lambda` |
| `pricing`                    | Various services      | N/A                 | Collects pricing for `Amazon RDS`, `Amazon EC2`, `Amazon ElastiCache`, `AWS Lambda`, `Amazon OpenSearch`, `AWS Compute Savings Plan` |
| `rds-usage`                  |  Amazon RDS           | Linked Account      | Collects CloudWatch metrics for chargeback |
| `transit-gateway`            |  AWS Transit Gateway  | Linked Account      | Collects CloudWatch metrics for chargeback |
| `ecs-chargeback`             |  Amazon ECS           | Linked Account      |  |
| `backup`                     |  AWS Backup           | Management Account  | Collects Backup Restore and Copy Jobs. Requires [activation of cross-account](https://docs.aws.amazon.com/aws-backup/latest/devguide/manage-cross-account.html#enable-cross-account) |
| `cost-optimization-hub`      |  AWS Cost Optimization Hub | Management Account  | Collects Detailed Reccomendations. Requires [activation](https://aws.amazon.com/aws-cost-management/cost-optimization-hub/faqs/#:~:text=You%20can%20enable%20Cost%20Optimization%20Hub%20by%20going%20to%20the,navigation%20bar%2C%20and%20click%20Enable.)  |
| `health-evetns`      |  AWS Health | Management Accounts  | Collect AWS Health notificaitons via AWS Organizational view  |
| `licence-manager`      |  AWS License Manager | Management Accounts  | Collect Licences and Grants |
| `SecurityHub-events`      |  AWS Security Hub | Management Account  | Collect AWS Security Hub Events via Event Bus from a single AWS organization |



### Installation

#### 1. In Management Account(s)

The Management Account stack makes use of [stack sets](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/what-is-cfnstacksets.html) configured to use [service-managed permissions](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html#stacksets-concepts-stackset-permission-models) to deploy stack instances to linked accounts in the AWS Organization.

Before creating the Management Account stack, please make sure [trusted access with AWS Organizations](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-orgs-activate-trusted-access.html) is activated.

The Management Account Stack creates a read role in the Management Account and also a StackSet that will deploy another read role in each linked Account. Permissions depend on the set of modules you activate via parameters of the stack:

   *  <kbd> <br> [Launch Stack >>](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?&templateURL=https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/data-collection/deploy-data-read-permissions.yaml&stackName=CidDataCollectionDataReadPermissionsStack&param_DataCollectionAccountID=REPLACE%20WITH%20DATA%20COLLECTION%20ACCOUNT%20ID&param_AllowModuleReadInMgmt=yes&param_OrganizationalUnitID=REPLACE%20WITH%20ORGANIZATIONAL%20UNIT%20ID&param_IncludeBudgetsModule=no&param_IncludeComputeOptimizerModule=no&param_IncludeCostAnomalyModule=no&param_IncludeECSChargebackModule=no&param_IncludeInventoryCollectorModule=no&param_IncludeRDSUtilizationModule=no&param_IncludeRightsizingModule=no&param_IncludeTAModule=no&param_IncludeTransitGatewayModule=no) <br> </kbd>


#### 2. In Data Collection Account

Deploy Data Collection Stack.

   * <kbd> <br> [Launch Stack >>](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?&templateURL=https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/data-collection/deploy-data-collection.yaml&stackName=CidDataCollectionStack&param_ManagementAccountID=REPLACE%20WITH%20MANAGEMENT%20ACCOUNT%20ID&param_IncludeTAModule=yes&param_IncludeRightsizingModule=no&param_IncludeCostAnomalyModule=yes&param_IncludeInventoryCollectorModule=yes&param_IncludeComputeOptimizerModule=yes&param_IncludeECSChargebackModule=no&param_IncludeRDSUtilizationModule=no&param_IncludeOrgDataModule=yes&param_IncludeBudgetsModule=yes&param_IncludeTransitGatewayModule=no)  <br> </kbd>

#### Usage
Check Athena tables.

### FAQ
#### Migration from previous Data Collection Lab

### See also
[CONTRIBUTING.md](CONTRIBUTING.md)

