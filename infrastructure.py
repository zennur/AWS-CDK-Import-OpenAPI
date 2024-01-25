import os
import pickle
import random
import secrets
import string
from uu import Error
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_cognito as cognito,
    aws_logs as logs,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_wafv2 as waf
)
from constructs import Construct
import yaml


class API(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        user_pool: cognito.UserPool,
        email_template_bucket: s3.Bucket,
        lambda_layer: lambda_.LayerVersion
    ):
        super().__init__(scope, id_)    

    def create_lambda_function(
            self, function_n, layer, role, environment_vars, prefix, duration=3
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
                function_name = prefix+function_n,
                code=lambda_.AssetCode("../Lambda/Functions/" + function_n + "/src"),
                handler="lambda_function.lambda_handler",
                runtime=lambda_.Runtime.PYTHON_3_10,
                layers=[layer],
                environment=environment_vars,
                role=role,
                timeout=Duration.seconds(duration),
            )

            return lambda_funct


    def create_api_gateway(
            self, path_to_api_doc, api, layer, role, environment_vars, prefix, authorizer):
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
            for path, methods in spec_file['paths'].items():
                # Split the path and filter out empty strings
                path_parts = [p for p in path.split('/') if p]

                # Track the current level of resource
                current_resource = api.root
                for part in path_parts:
                    resource_part = f'{{{part.strip("{}")}}}' if part.startswith('{') \
                        and part.endswith('}') else part

                    # Get or create a regular resource
                    current_resource = self.get_or_create_resource(
                        current_resource,
                        resource_part,
                        resource_map,
                        )
                    if part == path_parts[-1]:
                        # Add methods to the current resource
                        for method,_ in methods.items():

                            if method != "options":
                                function_name = spec_file["paths"][f"{path}"][f"{method}"][
                                    "operationId"
                                ]
                                function = self.get_or_create_lambda(
                                                function_name, function_list,
                                                layer,role, environment_vars, prefix)
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
                                            authorization_type=apigateway.AuthorizationType.CUSTOM)

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
        new_resource = parent_resource.add_resource(part,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
                allow_origins=apigateway.Cors.ALL_ORIGINS))
        resource_map[resource_id] = new_resource
        return new_resource

    def get_or_create_lambda(
            self, function_name, function_list, layer, role, environment_vars, prefix):
        """Function to create or get a Lambda function

        Args:
            function_name (_type_): _description_
            function_list (_type_): _description_
            layer (_type_): _description_
            role (_type_): _description_
            environment_vars (_type_): _description_
            prefix (_type_): _description_

        Returns:
            _type_: _description_
        """

        # Check if resource already exists in the map
        if function_name in function_list:
            return True

        # Create new resource if it doesn't exist
        new_function = self.create_lambda_function(
            function_name, layer, role, environment_vars, prefix)

        function_list[function_name] = new_function

        return new_function
    