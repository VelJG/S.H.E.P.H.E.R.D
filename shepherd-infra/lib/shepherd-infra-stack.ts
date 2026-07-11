import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cf from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as sagemaker from 'aws-cdk-lib/aws-sagemaker';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';

export class ShepherdInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const prefix = 'aabw-';

    // 1. Private Amazon S3 frontend bucket
    const frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `${prefix}shepherd-frontend-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // 2. Amazon CloudFront distribution
    // Create Origin Access Control (OAC)
    const oac = new cf.CfnOriginAccessControl(this, 'FrontendOAC', {
      originAccessControlConfig: {
        name: `${prefix}shepherd-frontend-oac`,
        originAccessControlOriginType: 's3',
        signingBehavior: 'always',
        signingProtocol: 'sigv4',
      },
    });

    const distribution = new cf.Distribution(this, 'FrontendDistribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(frontendBucket),
        viewerProtocolPolicy: cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
      ],
    });

    // Override distribution origin properties to use OAC instead of OAI (legacy)
    const cfnDistribution = distribution.node.defaultChild as cf.CfnDistribution;
    cfnDistribution.addPropertyOverride('DistributionConfig.Origins.0.OriginAccessControlId', oac.attrId);
    cfnDistribution.addPropertyOverride('DistributionConfig.Origins.0.S3OriginConfig.OriginAccessIdentity', '');

    // Grant CloudFront OAC read permissions on the frontend S3 bucket
    frontendBucket.addToResourcePolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject'],
      resources: [frontendBucket.arnForObjects('*')],
      principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
      conditions: {
        ArnEquals: {
          'AWS:SourceArn': `arn:aws:cloudfront::${this.account}:distribution/${distribution.distributionId}`,
        },
      },
    }));

    // 3. Private Amazon S3 evidence bucket
    const evidenceBucket = new s3.Bucket(this, 'EvidenceBucket', {
      bucketName: `${prefix}shepherd-evidence-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(7),
        },
      ],
    });

    // 4. Amazon ECR private repository
    const ecrRepo = new ecr.Repository(this, 'EcrRepo', {
      repositoryName: `${prefix}shepherd-inference-repo`,
      imageScanOnPush: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      emptyOnDelete: true,
    });

    ecrRepo.addLifecycleRule({
      maxImageCount: 3,
    });

    // 5. Amazon SageMaker AI placeholder resources
    const sagemakerRole = new iam.Role(this, 'SageMakerRole', {
      roleName: `${prefix}shepherd-sagemaker-role`,
      assumedBy: new iam.ServicePrincipal('sagemaker.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSageMakerFullAccess'),
      ],
    });

    sagemakerRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
      ],
      resources: [
        evidenceBucket.bucketArn,
        evidenceBucket.arnForObjects('*'),
      ],
    }));

    ecrRepo.grantPull(sagemakerRole);

    // We point to a standard public AWS Deep Learning Container (DLC) image for scaffolding,
    // as AWS SageMaker validates image existence upon Model creation.
    // When you are ready to use your custom YOLO inference image, push it to ECR and update this URI.
    const sagemakerModel = new sagemaker.CfnModel(this, 'SageMakerModelPlaceholder', {
      modelName: `${prefix}shepherd-yolo-model`,
      executionRoleArn: sagemakerRole.roleArn,
      primaryContainer: {
        image: `763104351884.dkr.ecr.${this.region}.amazonaws.com/pytorch-inference:2.0.0-cpu-py310`,
      },
    });

    const sagemakerEndpointConfig = new sagemaker.CfnEndpointConfig(this, 'SageMakerEndpointConfigPlaceholder', {
      endpointConfigName: `${prefix}shepherd-yolo-endpoint-config`,
      productionVariants: [
        {
          initialInstanceCount: 1,
          instanceType: 'ml.g4dn.xlarge',
          modelName: sagemakerModel.attrModelName,
          variantName: 'AllTraffic',
        },
      ],
    });

    // 6. Amazon API Gateway HTTP API
    const httpApi = new apigw.CfnApi(this, 'HttpApi', {
      name: `${prefix}shepherd-api`,
      protocolType: 'HTTP',
      corsConfiguration: {
        allowHeaders: ['content-type', 'authorization'],
        allowMethods: ['GET', 'POST', 'OPTIONS'],
        allowOrigins: ['*'],
      },
    });

    // 8. Amazon DynamoDB empty on-demand tables
    const venueMetricsTable = new dynamodb.Table(this, 'VenueMetricsTable', {
      tableName: `${prefix}VenueMetrics`,
      partitionKey: { name: 'zoneId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'timestamp', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const incidentsTable = new dynamodb.Table(this, 'IncidentsTable', {
      tableName: `${prefix}Incidents`,
      partitionKey: { name: 'incidentId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const operationalTasksTable = new dynamodb.Table(this, 'OperationalTasksTable', {
      tableName: `${prefix}OperationalTasks`,
      partitionKey: { name: 'taskId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // 7. AWS Lambda function execution role
    const lambdaRole = new iam.Role(this, 'LambdaRole', {
      roleName: `${prefix}shepherd-lambda-role`,
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    venueMetricsTable.grantReadWriteData(lambdaRole);
    incidentsTable.grantReadWriteData(lambdaRole);
    operationalTasksTable.grantReadWriteData(lambdaRole);
    evidenceBucket.grantReadWrite(lambdaRole);

    const healthLambda = new lambda.Function(this, 'HealthLambda', {
      functionName: `${prefix}shepherd-health-check`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'health.handler',
      code: lambda.Code.fromAsset('lambda'),
      role: lambdaRole,
      environment: {
        ENVIRONMENT: 'hackathon',
        VENUE_METRICS_TABLE: venueMetricsTable.tableName,
        INCIDENTS_TABLE: incidentsTable.tableName,
        OPERATIONAL_TASKS_TABLE: operationalTasksTable.tableName,
        EVIDENCE_BUCKET_NAME: evidenceBucket.bucketName,
      },
    });

    // API Gateway Lambda Integration permissions & resources
    new lambda.CfnPermission(this, 'ApiGatewayInvokePermission', {
      action: 'lambda:InvokeFunction',
      functionName: healthLambda.functionArn,
      principal: 'apigateway.amazonaws.com',
      sourceArn: `arn:aws:execute-api:${this.region}:${this.account}:${httpApi.ref}/*/*/*`,
    });

    const integration = new apigw.CfnIntegration(this, 'LambdaIntegration', {
      apiId: httpApi.ref,
      integrationType: 'AWS_PROXY',
      integrationUri: healthLambda.functionArn,
      payloadFormatVersion: '2.0',
    });

    new apigw.CfnRoute(this, 'HealthRoute', {
      apiId: httpApi.ref,
      routeKey: 'GET /health',
      target: `integrations/${integration.ref}`,
    });

    new apigw.CfnStage(this, 'ApiStage', {
      apiId: httpApi.ref,
      stageName: '$default',
      autoDeploy: true,
    });

    // 10. Tags
    cdk.Tags.of(this).add('Project', 'SHEPHERD');
    cdk.Tags.of(this).add('Environment', 'hackathon');

    // Stack Outputs
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: `https://${distribution.distributionDomainName}`,
      description: 'CloudFront Distribution URL',
    });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: `https://${httpApi.ref}.execute-api.${this.region}.amazonaws.com`,
      description: 'API Gateway Base URL',
    });

    new cdk.CfnOutput(this, 'FrontendBucketName', {
      value: frontendBucket.bucketName,
      description: 'Frontend S3 Bucket Name',
    });

    new cdk.CfnOutput(this, 'EvidenceBucketName', {
      value: evidenceBucket.bucketName,
      description: 'Evidence S3 Bucket Name',
    });

    new cdk.CfnOutput(this, 'EcrRepoUri', {
      value: ecrRepo.repositoryUri,
      description: 'ECR Repository URI',
    });

    new cdk.CfnOutput(this, 'VenueMetricsTableName', {
      value: venueMetricsTable.tableName,
    });

    new cdk.CfnOutput(this, 'IncidentsTableName', {
      value: incidentsTable.tableName,
    });

    new cdk.CfnOutput(this, 'OperationalTasksTableName', {
      value: operationalTasksTable.tableName,
    });

    new cdk.CfnOutput(this, 'SageMakerRoleArn', {
      value: sagemakerRole.roleArn,
      description: 'SageMaker Execution Role ARN',
    });
  }
}
