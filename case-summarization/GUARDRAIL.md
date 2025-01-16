## AWS Bedrock Guardrail
Amazon Bedrock Guardrail is a crucial security feature for generative AI applications that helps implement safeguards based on specific use cases and responsible AI policies. It provides an additional layer of protection on top of the native safeguards offered by foundation models (FMs)[1][2].

## Key Features and Importance

Amazon Bedrock Guardrails offers several important security features:

1. **Content Filtering**: It helps block harmful content by evaluating both user inputs and model responses. The system can filter out content related to hate speech, insults, sexual content, violence, and misconduct[2].

2. **Topic Restrictions**: Organizations can define specific topics to avoid, ensuring that interactions remain relevant to their business and align with company policies[2].

3. **Sensitive Information Protection**: The system can detect and redact personally identifiable information (PII) in user inputs and model responses, helping to protect user privacy[2][3].

4. **Custom Word Filtering**: It allows the configuration of custom words or phrases to be blocked, including profanity or specific terms like competitor names[2].

5. **Hallucination Detection**: Contextual grounding checks help detect and filter out hallucinations in model responses, ensuring more accurate and trustworthy information[2].

## Security Importance

The importance of Amazon Bedrock Guardrails for security cannot be overstated:

1. **Enhanced Content Safety**: It can block up to 85% more harmful content compared to native FM protections, significantly improving the safety of AI applications[2].

2. **Consistent Security Across Models**: Guardrails work with all large language models in Amazon Bedrock, providing a uniform level of security regardless of the underlying model[2].

3. **Customizable Safeguards**: Organizations can create multiple guardrails with different configurations, tailoring security measures to specific applications and use cases[1][3].

4. **Compliance and Responsible AI**: By allowing fine-tuned control over content and interactions, Guardrails help organizations adhere to their responsible AI policies and maintain regulatory compliance[2].

5. **Protection Against Prompt Attacks**: The system safeguards against prompt injection and jailbreak attempts, enhancing overall security[2].

Amazon Bedrock Guardrails plays a vital role in ensuring that generative AI applications remain safe, relevant, and aligned with organizational policies. By providing robust, customizable security features, it enables businesses to leverage the power of AI while mitigating potential risks associated with harmful or inappropriate content[1][2][3].

### Reasonable Defaults

This plugin comes with the following reasonable defaults that can be overriden through the parameters exposed by the CloudFormation template:

| Parameter | Description | Default |
| --- | --- | --- |
| BlockedInputMessage | Message to return when the Amazon Bedrock Guardrail blocks a prompt. | {"executive_summary":"Amazon Bedrock Guardrails has blocked the AWS Support Case Summarization.","proposed_solutions":"","actions":"","references":[],"tam_involved":"","feedback":""} |
| BlockedOutputMessage | Message to return when the Amazon Bedrock Guardrail blocks a model response | '' |
| IncludeSexualContentFilter | Whether to include Sexual Content Filter in the Guardrail or not | 'yes' |
| SexualContentFilterInputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces. | 'HIGH' |
| SexualContentFilterOutputStrength | The strength of the content filter to apply to model responses. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| IncludeViolentContentFilter | Whether to include Violent Content Filter in the Guardrail or not | 'yes' |
| ViolentContentFilterInputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| ViolentContentFilterOutputStrength | The strength of the content filter to apply to model responses. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| IncludeHateContentFilter | Whether to include Violent Content Filter in the Guardrail or not | 'yes' |
| HateContentFilterInputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| HateContentFilterOutputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| IncludeInsultsContentFilter | Whether to include Insults Content Filter in the Guardrail or not | 'yes' |
| InsultsContentFilterInputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| InsultsContentFilterOutputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| IncludeMisconductContentFilter | Whether to include Insults Content Filter in the Guardrail or not | 'yes' |
| MisconductContentFilterInputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| MisconductContentFilterOutputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |
| IncludePromptAttackContentFilter | Whether to include Insults Content Filter in the Guardrail or not | 'yes' |
| PromptAttackContentFilterInputStrength | The strength of the content filter to apply to prompts. As you increase the filter strength, the likelihood of filtering harmful content increases and the probability of seeing harmful content in your application reduces | 'HIGH' |

### References & Further reading

* [1] How Amazon Bedrock Guardrails works https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html
* [2] Generative AI Data Governance - Amazon Bedrock Guardrails - AWS https://aws.amazon.com/bedrock/guardrails/
* [3] Stop harmful content in models using Amazon Bedrock Guardrails https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html

## Usage

This stack will deploy a minimalistic Amazon Bedrock Guardrail that will filter out any inputs or outputs that can be assimilated to prompt hacking, sexual, violent, misconduct, hatred speech or insults. Any additional fine-tuning of filters can be acheived by customizing this template.

## Support and Contribution

See [CONTRIBUTING](../../../CONTRIBUTING.md) for more information.

## Security

See [SECURITY](../../../SECURITY.md) for more information.

## License

This project is licensed under the Apache-2.0 License.

