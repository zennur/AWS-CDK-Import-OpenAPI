# AWS CDK Import OpenAPI
### Seamlessly use OpenAPI spec to generate all the API Gateway resources in AWS CDK

This repository contains a Python module that automates the creation of AWS infrastructure using the AWS Cloud Development Kit (CDK). It dynamically generates AWS Lambda functions and an API Gateway based on an OpenAPI specification file. This tool is designed to help developers quickly deploy serverless architectures that are defined by OpenAPI specs.

### Features
<b> Automatic Lambda Function Creation: </b> Generates AWS Lambda functions for each endpoint defined in the OpenAPI specification.
<b> API Gateway Integration: </b> Sets up an API Gateway that routes requests to the corresponding Lambda functions.
<b> Flexible Deployment: </b> Integrates with AWS IAM, S3, Cognito, CloudFront, and other AWS services to provide a comprehensive and secure environment.
<b> Customizable: </b> Allows for custom configurations of Lambda functions and API Gateway settings.

### Prerequisites
To use this module, you will need:

AWS CLI installed and configured with appropriate permissions.
Python 3.8 or higher.
AWS CDK installed.
An OpenAPI specification file in YAML format.

### Installation
Clone this repository to your local machine using:
```shell
git clone https://github.com/zennur/AWS-CDK-Import-OpenAPI.git
```

Navigate into the repository directory:
```shell
cd aws-cdk-openapi-importer
```

Install required dependencies:
```shell
pip install -r requirements.txt
```

### Usage
<b> Prepare Your OpenAPI Specification: <b> Ensure your OpenAPI YAML file is ready and located within your project directory.
<b> Configure the CDK Stack: <b> Modify the API class within the api.py file to customize the AWS environment according to your needs.
<b> Deploy: <b> Run the following commands to deploy your infrastructure to AWS:
```shell
cdk bootstrap
cdk deploy
```

### API Class Reference
create_lambda_function: Creates a Lambda function based on parameters such as function name, Lambda layer, IAM role, and environment variables.
create_api_gateway: Sets up the API Gateway resources and methods defined in your OpenAPI specification file.
get_or_create_resource: Helper function to create or retrieve API Gateway resources.
get_or_create_lambda: Helper function to create or retrieve Lambda functions if they don't already exist.

### Contributing
Contributions are welcome! Feel free to fork the repository and submit pull requests.

### License
This project is licensed under the MIT License - see the LICENSE file for details.
