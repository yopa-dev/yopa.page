---
title: "Deploy a Serverless API Safely with AWS CDK v2"
date: 2023-06-05T01:25:00-04:00
lastmod: 2026-08-01
reviewed_at: 2026-08-01
maintenance_status: replacement
replaces_url: "/blog/2023-06-05-deploying-services-aws-cdk-and-aws-sso.html"
author: Yoonsoo Park
description: "A current CDK v2 workflow for API Gateway, Lambda, and S3 using supported runtimes, temporary credentials, tests, and least privilege."
categories:
  - AWS
  - Infrastructure as Code
tags:
  - AWS CDK
  - AWS Lambda
  - Amazon API Gateway
  - Amazon S3
  - IAM Identity Center
---

Older CDK examples often mix `@aws-cdk/*` v1 modules with `aws-cdk-lib`, target retired Lambda runtimes, and treat deployment credentials as application configuration. A current workflow uses CDK v2 consistently, an actively supported runtime, temporary operator credentials, and a reviewable synthesized template.

> **Review note (2026-10-21):** The example runtime changed from `Runtime.NODEJS_22_X` to `Runtime.NODEJS_24_X`. Lambda's `nodejs22.x` is still supported, but its deprecation is scheduled for April 30, 2027. `nodejs24.x` is scheduled for April 30, 2028 ([Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)). Changing the runtime of an existing function is a deployment: run `cdk diff` first and test the handler on Node.js 24.

## Choose the API deliberately

API Gateway HTTP APIs are usually the lower-cost, lower-complexity choice for Lambda proxy APIs. REST APIs remain appropriate when you need features specific to that product, such as usage plans or certain request transformations. A Lambda Function URL may fit a very small service with simple authorization, while an Application Load Balancer is often a better match for an existing container service.

The following example keeps REST API because it mirrors the older article, but the choice should be explicit.

## CDK v2 stack

```bash
mkdir current-api && cd current-api
npx aws-cdk@latest init app --language typescript
npm install aws-cdk-lib constructs
```

```typescript
import { Stack, StackProps, RemovalPolicy } from "aws-cdk-lib";
import { Construct } from "constructs";
import { Runtime, Function, Code } from "aws-cdk-lib/aws-lambda";
import { RestApi, LambdaIntegration } from "aws-cdk-lib/aws-apigateway";
import { Bucket, BlockPublicAccess } from "aws-cdk-lib/aws-s3";

export class ApiStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const bucket = new Bucket(this, "Data", {
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
    });

    const handler = new Function(this, "Handler", {
      runtime: Runtime.NODEJS_24_X,
      handler: "index.handler",
      code: Code.fromAsset("lambda"),
      environment: { BUCKET_NAME: bucket.bucketName },
    });

    bucket.grantRead(handler);
    const api = new RestApi(this, "Api");
    api.root.addMethod("GET", new LambdaIntegration(handler));
  }
}
```

`grantRead` creates a scoped identity policy for the function. It does not mean CDK inferred every permission your code might need. Review the synthesized IAM statements and avoid wildcard grants.

## Authenticate, inspect, deploy

```bash
aws sso login --profile engineering-dev
AWS_PROFILE=engineering-dev aws sts get-caller-identity
AWS_PROFILE=engineering-dev npx cdk bootstrap
npx cdk synth
npx cdk diff
AWS_PROFILE=engineering-dev npx cdk deploy --require-approval broadening
```

Bootstrap once per account and Region using an authorized deployment role. Commit `cdk.json`, source, lockfile, and tests—not `cdk.out`. Pin the CDK library range and update it deliberately. In CI, use OIDC to assume a deploy role instead of storing access keys.

## Production gaps the small example does not solve

Add structured logs, alarms, tracing where justified, throttling, an authorization mechanism, input validation, and an explicit data-retention decision. Package dependencies reproducibly. Test the Lambda handler separately and assert the CDK template for security-sensitive properties. Deploy to a non-production account first and keep rollback behavior clear; retained buckets and databases need their own migration and deletion process.

## Migration checklist

- Remove CDK v1 service packages and import services from `aws-cdk-lib`.
- Import `Construct` from `constructs`.
- Select a currently supported Lambda runtime and test the application on it.
- Replace explicit keys with Identity Center locally and OIDC/roles in CI.
- Run `synth`, tests, security checks, and `diff` before deployment.
- Inspect IAM broadening and replacement/destruction in the change set.
- Verify the deployed endpoint, logs, authorization, S3 access, and rollback.

CDK gives higher-level constructs and reusable TypeScript, but CloudFormation or SAM may be simpler when the infrastructure is small, while Terraform/OpenTofu may fit a multi-provider estate. Choose based on team ownership and lifecycle, not language preference alone.

## Test the infrastructure contract

CDK assertions catch regressions before CloudFormation receives them. A focused test should verify properties whose accidental removal would change the security or durability boundary: supported runtime, private bucket, TLS enforcement, retention policy, and narrow grants. Do not snapshot the entire synthesized template; broad snapshots are noisy and reviewers often approve them without understanding a changed IAM statement.

After deployment, invoke the endpoint with an authorized and unauthorized caller, inspect the function logs, put a known object in the bucket, and confirm the function can read it but cannot write or list unrelated buckets. Then exercise rollback from a deliberately broken application version. CloudFormation rollback does not automatically reverse data migrations, so keep stateful changes separate from routine function deployment.

If the API is internet-facing, add an explicit abuse plan: route throttles, account concurrency protection, payload limits, WAF only where its rules solve a known threat, and cost alarms. If it is internal, verify the resource policy, authorizer, DNS, and network path from the real caller. “The stack deployed” is only a structural check; it does not prove the API is operable or appropriately authorized.

Verified on **2026-08-01**.

## Official sources

- [AWS CDK v2 Developer Guide](https://docs.aws.amazon.com/cdk/v2/guide/home.html)
- [AWS Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)
- [CDK permissions and grants](https://docs.aws.amazon.com/cdk/v2/guide/permissions.html)
- [API Gateway API types](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vs-rest.html)
