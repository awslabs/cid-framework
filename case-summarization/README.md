## AWS Support Case Summarization Plugin

### About

This plugin is aimed at augmenting the exerience of the AWS Support Cases Radar which is part of the [Cloud Intelligence Dashboards Framework](https://catalog.workshops.aws/awscid) by leveraging Generative AI powered by Amazon Bedrock to summarize AWS Support Case Communications and help customers achieve operation excellence.

This plugin contains the following elements:
* [case-summarization](README.md) - a CloudFormation Template for deploying the AWS Support Case Summarization Plugin that integrates seamlessly with the Data Collection Framework.
* [guardrails](/plugins/support-case-summarization/deploy/deploy-bedrock-guardails/README.md) - a CloudFormation Template for deploying a minimalistic setup of Amazon Bedrock Guardrail.Customers that haven't designed and deployed one already, could use this template as a quickstart. 

### Architecture

![Architecture](/plugins/support-case-summarization/images/archi.png)

### Reasonable Defaults

This plugin comes with the following reasonable defaults that can be overriden through the parameters exposed by the CloudFormation template:

| Parameter | Description | Default |
| --- | --- | --- |
| BedrockRegion | The AWS Region from which the Summarization is performed | us-east-1 |
| Instructions | Additional instructions passed to the Large Language Model for the summarization process customizability | '' |
| Provider | Large Language Model Provider for the summarization process customizability | Anthropic |
| FoundationModel | Foundation Model to be used for the summarization process | Claude 3.5 Sonnet |
| InferenceType | Summarization process Inference Type | 'ON_DEMAND' |
| Temperature | Summarization process Temperature | 0 |
| MaxTokens | Summarization process Maximum Tokens | 8096 |
| MaxRetries | Summarization process Maximum Retries | 30 |
| Timeout | Summarization process Timeout in seconds | 60 |
| BatchSize | Summarization process Batch Size for parallel processing | 1 |

### Installation

#### 1. Enable Amazon Bedrock Target Model Access In the Data Collection Account

- See [Add or remove access to Amazon Bedrock foundation models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html) for guidance.

#### 2. In case you do not have one already, Deploy an Amazon Bedrock Guardrail in the Data Collection Account

- See [Stop harmful content in models using Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) for comprehensive documentation on how to use and deploy Amazon Bedrock Guardrails.
- See [deploy-bedrock-guardrails](/plugins/support-case-summarization/deploy/deploy-bedrock-guardails/README.md) for a quickstart, but not comprehensive, template.

#### 2. Deploy the AWS Support Case Summarization Stack In the Data Collection Account

    * <kbd> <br> [Launch Stack >>](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?&templateURL=https://aws-managed-cost-intelligence-dashboards-us-east-1.s3.amazonaws.com/cfn/plugins/support-case-summarization/deploy/case-summarization.yaml&stackName=CidSupportCaseSummarizationStack&param_BedrockRegion=REPLACE%20WITH%20TARGET%20REGION)  <br> </kbd>

## Support and Contribution

See [CONTRIBUTING](CONTRIBUTING.md) for more information.

## Security

See [SECURITY](SECURITY.md) for more information.

## Limitations

As of today, the AWS Support Cases Summarization plugin does not make use of Amazon Guardrails.
Amazon Bedrock Guardrails is a crucial security feature for generative AI applications that helps implement safeguards based on specific use cases and responsible AI policies. It provides an additional layer of protection on top of the native safeguards offered by foundation models (FMs).

This feature will be added in a future release.

### Further Reading

* [1] How Amazon Bedrock Guardrails works https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html
* [2] Generative AI Data Governance - Amazon Bedrock Guardrails - AWS https://aws.amazon.com/bedrock/guardrails/
* [3] Stop harmful content in models using Amazon Bedrock Guardrails https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html

## License

This project is licensed under the Apache-2.0 License.
