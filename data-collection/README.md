## CID Data Collection

This projects demonstrates usage of AWS API for collecting various types of usage data.

![Architecture](data-collection/images/archi.png)

1. Amazon EventBridge rule invokes Step Function of every every deployed data collection module. based on schedule.
2. The Step Function launches a Lambda function Account Collector that assumes Read Role role in the Management account and retrieves linked accounts list via AWS Organizations API
3. Step Functions launches Data Collection Lambda function for each collected Account.
4. Each data collection module Lambda function assumes IAM role in linked accounts and retrieves respective optimization data via AWS SDK for Python. Retrieved data aggregated in Amazon S3 bucket
5. Once data stored in S3 bucket, Step Functions triggers AWS Glue crawler which creates or updates the table in Glue Data Catalog
6. Collected data visualized with the Cloud Intelligence Dashboards using Amazon QuickSight to get optimization recommendations and insights


List of modules and objects collected:

* organization
* budgets
* trusted-advisor
* compute-optimizer
* cost-explorer-cost-anomaly
* cost-explorer-rightsizing
* inventory
  * OpensearchDomains, ElasticacheClusters, RdsDbInstances, EBS, AMI, Snapshot
* pricing
  * AmazonRDS, AmazonEC2, AmazonElastiCache, AmazonES, AWSComputeSavingsPlan
* rds-usage
* transit-gateway (chargeback)
* ecs-chargeback
