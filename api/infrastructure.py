"""_summary_

Returns:
    _type_: _description_
"""
import os
import pickle
import yaml
from aws_cdk import (
    Duration,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cognito as cognito,
)
from constructs import Construct

UNPROTECTED_PATHS = [
    "/auth/confirm-user",
]

class API(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        user_pool: cognito.UserPool,
        lambda_layer: lambda_.LayerVersion,
    ):
        super().__init__(scope, id_)
        api_name = "HelloWorldAPI"
        # create iam role for lambda execution, sns access and dynamodb access
        lambda_role = iam.Role(
            self,
            "lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonDynamoDBFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSNSFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSQSFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonCognitoPowerUser"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSESFullAccess"),
            ],
        )

        authorizer_role = iam.Role(
            self,
            "LambdaAuthorizerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Lambda Authorizer",
        )

        authorizer_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            )
        )

        authorizer_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:GetUser",
                    "cognito-idp:GetUserPoolMfaConfig",
                    "cognito-idp:ListUsers",
                ],
                resources=[
                    f"arn:aws:cognito-idp:*:*:userpool/{user_pool.user_pool_id}"
                ],
            )
        )

        env_vars = {}

        self.authorizer_lambda = self.create_lambda_function(
            "Authorizer", lambda_layer, authorizer_role, env_vars
        )

        self.operational_lambda = self.create_lambda_function(
            "OperationalLambda", lambda_layer, lambda_role, env_vars
        )

        self.authorizer = apigateway.TokenAuthorizer(
            self,
            "Authorizer",
            handler=self.authorizer_lambda,
            identity_source="method.request.header.Authorization",
        )

        api_role = iam.Role(
            self,
            "apiRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )

        api_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=["*"],
                actions=[
                    "lambda:InvokeFunction",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                    "logs:GetLogEvents",
                    "logs:FilterLogEvents",
                ],
            )
        )
        api = apigateway.LambdaRestApi(
            self,
            api_name,
            handler=self.operational_lambda,
            default_cors_preflight_options={
                "allow_origins": ["*"],
                "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": [
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent",
                ],
                "allow_credentials": False,
            },
            proxy=False,
            default_method_options=apigateway.MethodOptions(
                authorizer=self.authorizer_lambda
            ),
            deploy_options=apigateway.StageOptions(
                stage_name=os.environ["BITBUCKET_DEPLOYMENT_ENVIRONMENT"],
                data_trace_enabled=True,
                tracing_enabled=True,
                caching_enabled=False,
            ),
        )

        

        self.create_api_gateway(
            "../openapi/openapi.yaml",
            api,
            lambda_layer,
            lambda_role,
            env_vars,
            self.authorizer,
        )

        api_plan = api.add_usage_plan("APIUsagePlan")
        # api_plan.add_api_key(api_key)

        api_plan.add_api_stage(api=api, stage=api.deployment_stage)



    def create_api_gateway(
            self, path_to_api_doc, api, layer, role, environment_vars, authorizer
        ):
            """_summary_

            Args:
                path_to_api_doc (_type_): _description_
                api (_type_): _description_
                layer (_type_): _description_
                role (_type_): _description_
                environment_vars (_type_): _description_
                prefix (_type_): _description_
                authorizer_lambda (_type_): _description_
                authorizer (_type_): _description_
            """
            spec_file = ""
            resource_map = {}
            function_list = {}
            with open(path_to_api_doc, "r") as stream:
                spec_file = pickle.loads(pickle.dumps(yaml.safe_load(stream)))
                for path, methods in spec_file["paths"].items():
                    # Split the path and filter out empty strings
                    path_parts = [p for p in path.split("/") if p]

                    # Track the current level of resource
                    current_resource = api.root
                    for part in path_parts:
                        resource_part = (
                            f'{{{part.strip("{}")}}}'
                            if part.startswith("{") and part.endswith("}")
                            else part
                        )

                        # Get or create a regular resource
                        current_resource = self.get_or_create_resource(
                            current_resource,
                            resource_part,
                            resource_map,
                        )
                        if part == path_parts[-1]:
                            # Add methods to the current resource
                            for method, _ in methods.items():
                                if method != "options":
                                    function_name = spec_file["paths"][f"{path}"][
                                        f"{method}"
                                    ]["operationId"]
                                    function = self.get_or_create_lambda(
                                        function_name,
                                        function_list,
                                        layer,
                                        role,
                                        environment_vars,
                                    )
                                    if function is not True:
                                        http_method = method.upper()
                                        if path in UNPROTECTED_PATHS:
                                            current_resource.add_method(
                                                http_method,
                                                apigateway.LambdaIntegration(function),
                                            )
                                        else:
                                            current_resource.add_method(
                                                http_method,
                                                apigateway.LambdaIntegration(function),
                                                authorizer=authorizer,
                                                authorization_type=apigateway.AuthorizationType.CUSTOM,
                                            )

    def get_or_create_resource(self, parent_resource, part, resource_map):
        """Function to create or get an API Gateway resource

        Args:
            parent_resource (_type_): _description_
            part (_type_): _description_
            resource_map (_type_): _description_

        Returns:
            _type_: _description_
        """
        # Construct the unique identifier for the resource
        resource_id = f"{parent_resource.node.path}/{part}"

        # Check if resource already exists in the map
        if resource_id in resource_map:
            return resource_map[resource_id]
        # Create new resource if it doesn't exist
        new_resource = parent_resource.add_resource(
            part,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                allow_origins=apigateway.Cors.ALL_ORIGINS,
            ),
        )
        resource_map[resource_id] = new_resource
        return new_resource

    def get_or_create_lambda(
        self, function_name, function_list, layer, role, environment_vars
    ):
        """Function to create or get a Lambda function

        Args:
            function_name (_type_): _description_
            function_list (_type_): _description_
            layer (_type_): _description_
            role (_type_): _description_
            environment_vars (_type_): _description_

        Returns:
            _type_: _description_
        """

        # Check if resource already exists in the map
        if function_name in function_list:
            return True

        # Create new resource if it doesn't exist
        new_function = self.create_lambda_function(
            function_name, layer, role, environment_vars
        )

        function_list[function_name] = new_function

        return new_function
    
    def create_lambda_function(
        self, function_n, layer, role, environment_vars, duration=6
    ):
        """Create lambda function with given parameters

        Args:
            function_n (str): Function name
            layer (lambda_.LayerVersion): lambda layer
            role (iam.Role): role for the function
            environment_vars (list): list of lambda environment variables
            prefix (str): lambda function prefix
            duration (int, optional): Lambda timeout duration. Defaults to 3.

        Returns:
            lambda_.Function: Lambda function created
        """
        lambda_funct = lambda_.Function(
            self,
            function_n,
            code=lambda_.AssetCode("../Lambda/Functions/" + function_n + "/src"),
            handler="lambda_function.lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_10,
            layers=[layer],
            environment=environment_vars,
            role=role,
            timeout=Duration.seconds(duration),
        )

        return lambda_funct
    