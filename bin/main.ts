#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DynamodbAccessControlSaasStack } from '../lib/dynamodb-access-control-saas-stack';

const app = new cdk.App();
new DynamodbAccessControlSaasStack(app, 'DynamodbAccessControlSaasStack');