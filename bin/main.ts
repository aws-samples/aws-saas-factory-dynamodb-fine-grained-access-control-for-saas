#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DynamodbAccessControlSaasStack } from '../lib/dynamodb-access-control-saas-stack';
import { AwsSolutionsChecks } from 'cdk-nag'
import { Aspects } from 'aws-cdk-lib';

const app = new cdk.App();
new DynamodbAccessControlSaasStack(app, 'DynamodbAccessControlSaasStack');
/**
 * Following code is for cdk-nag testing purposes.
 */
// Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }))
// new DynamodbAccessControlSaasStack(app, 'DynamodbAccessControlSaasStack', {});
