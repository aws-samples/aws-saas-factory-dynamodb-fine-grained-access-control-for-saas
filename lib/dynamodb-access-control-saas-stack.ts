import {Stack, StackProps, CfnOutput, Duration} from 'aws-cdk-lib';
import {
    aws_lambda as lambda,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigw,
    aws_logs as logs
} from 'aws-cdk-lib';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import {Construct} from 'constructs';

/**
 * CDK Stack Class that integrates deploys the AWS services to run the
 * DynamoDB Fine-Grained-Access-Control demo solution
 */
export class DynamodbAccessControlSaasStack extends Stack {
    constructor(scope: Construct, id: string, props?: StackProps) {
        super(scope, id, props);

        const table = new dynamodb.Table(this, 'DDBFGACItemsTable', {
            partitionKey: {name: 'ShardID', type: dynamodb.AttributeType.STRING},
            sortKey: {name: 'ProductId', type: dynamodb.AttributeType.STRING}
        });

        const lambdaServiceRole = new iam.Role(this, 'DDBFGACLambdaServiceRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
            ]
        });

        const ddbQueryPermissionPolicy = new PolicyStatement({
            effect: Effect.ALLOW,
            resources: [table.tableArn],
            actions: [
                "dynamodb:Query"
            ]
        });
        lambdaServiceRole.addToPolicy(ddbQueryPermissionPolicy);

        const tenantAssumeRole = new iam.Role(this, 'DDBFGACTenantAssumeRole', {
            assumedBy: new iam.ArnPrincipal(lambdaServiceRole.roleArn)
        });

        const describeAcmCertificates = new PolicyStatement({
            effect: Effect.ALLOW,
            resources: [table.tableArn],
            actions: [
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem",
                "dynamodb:DeleteItem",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:Query",
                "dynamodb:UpdateItem"
            ]
        });
        tenantAssumeRole.addToPolicy(describeAcmCertificates);


        const lambdaHander = new lambda.Function(this, "DDBFGACItemService", {
            role: lambdaServiceRole,
            runtime: lambda.Runtime.PYTHON_3_11,
            code: lambda.Code.fromAsset("resources"),
            handler: "lambda_function.lambda_handler",
            timeout: Duration.seconds(30),
            environment: {
                DYNAMO_TABLE_ARN: table.tableArn,
                DYNAMO_TABLE_NAME: table.tableName,
                DYNAMO_ASSUME_ROLE_ARN: tenantAssumeRole.roleArn,
                AWS_REGION_NAME: this.region
            }
        });
        
        const prdLogGroup = new logs.LogGroup(this, "APIGWAccessLogs");
        
        const restApi = new apigw.RestApi(this, 'DDBFGACApiGateway', {
            deployOptions: {
                accessLogDestination: new apigw.LogGroupLogDestination(prdLogGroup),
                accessLogFormat: apigw.AccessLogFormat.jsonWithStandardFields({
                caller: true,
                httpMethod: true,
                ip: true,
                protocol: true,
                requestTime: true,
                resourcePath: true,
                responseLength: true,
                status: true,
                user: true,
            }),
            },
        });

        const apiModel = new apigw.Model(this, "model-validator", {
            restApi: restApi,
            contentType: "application/json",
            description: "To validate the request body",
            modelName: "ddbfgacapimodel",
            schema: {
                type: apigw.JsonSchemaType.OBJECT,
                required: ["tenant_id"],
                properties: {
                    tenant_id: { type: apigw.JsonSchemaType.STRING }
                },
            },
        });


        const itemResource = restApi.root.addResource('items');
        itemResource.addMethod("POST",
            new apigw.LambdaIntegration(lambdaHander), {
                authorizationType: apigw.AuthorizationType.IAM,
                requestValidator: new apigw.RequestValidator(
                    this,
                    "body-validator",
                    {
                        restApi: restApi,
                        requestValidatorName: "body-validator",
                        validateRequestBody: true
                    }
                ),
                requestModels: {
                    "application/json": apiModel
                },
            });

        itemResource.addMethod("GET",
            new apigw.LambdaIntegration(lambdaHander), {
                authorizationType: apigw.AuthorizationType.IAM,
                requestParameters: {
                    'method.request.querystring.tenant_id': true
                    },
                    requestValidatorOptions: {
                    validateRequestParameters: true,
                    },
                
            });

        new CfnOutput(this, 'AWS-Account-Id', {value: this.account});
        new CfnOutput(this, 'AWS-Region', {value: this.region});
        new CfnOutput(this, 'API Endpoint', {value: restApi.url});

    }

}

