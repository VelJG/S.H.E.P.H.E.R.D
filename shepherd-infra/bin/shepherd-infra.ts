#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { ShepherdInfraStack } from '../lib/shepherd-infra-stack';

const app = new cdk.App();
new ShepherdInfraStack(app, 'ShepherdInfraStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || process.env.AWS_DEFAULT_REGION || 'ap-southeast-1',
  },
});
