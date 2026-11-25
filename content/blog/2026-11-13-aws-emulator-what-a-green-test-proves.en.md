---
title: "AWS Emulator passed my tests. Which of those passes would hold on real AWS?"
date: 2026-11-13T09:00:00-05:00
author: Yoonsoo Park
description: "AWS shipped a free local emulator on 2026-11-11. I ran 13 CI-style checks against v1.0.343 with no network and no AWS account. Conditional writes, create-only puts, IAM denies, and SQS visibility matched AWS documentation. A Bedrock call returned a cheerful placeholder, a GSI never lagged, and two policy checks behaved the opposite of the emulator's own security page."
categories:
  - AWS
  - Testing
tags:
  - AWS Emulator
  - DynamoDB
  - Amazon Bedrock
  - CI
  - measured
---

On 2026-11-11 AWS announced [AWS Emulator](https://aws.amazon.com/about-aws/whats-new/2026/11/aws-emulator-now-available/), a free program that pretends to be AWS on your own machine. Your existing SDK and CLI calls go to `127.0.0.1` instead of the cloud, resources live in memory, and there is no AWS account involved. The announcement makes a strong promise:

> For the operations it supports, AWS Emulator returns the same result as AWS for valid calls and the same errors for invalid ones. Operations it doesn't yet support return 501 Not Implemented.

That promise is what decides whether you can move an integration test off a real AWS account. If the test is green locally, does that green mean anything on AWS?

So I took one release, **v1.0.343** (release 2026.11.13), and ran the kinds of assertions I actually see in CI suites. Short answer:

1. **Conditional writes, create-only puts, IAM denies, SQS visibility timeouts, and input validation matched AWS documentation.** Tests built on these can move.
2. **A Bedrock `Converse` call succeeded with a placeholder reply** that says no model runs in the emulator. A test that only checks "the reply is not empty" passes and proves nothing.
3. **A DynamoDB global secondary index (GSI) never lagged:** 200 reads straight after 200 writes all found the item. On AWS, GSIs are eventually consistent, so the same test can flake.
4. **AgentCore `InvokeAgentRuntime` returned 501.** At least that one fails loudly.
5. **A bucket-policy deny and a KMS key-policy deny were enforced,** although the emulator's security page says it doesn't check either. The page is right about the only thing that matters: don't use the emulator to test security in either direction.

Code and raw output: [yopa-experiments `experiment/aws-emulator-ci-fidelity-20261113`](https://github.com/ypark9/yopa-experiments/tree/experiment/aws-emulator-ci-fidelity-20261113/aws-emulator-ci-fidelity) (commit `8b64f58`).

## How I ran it without touching AWS

| Guard | Why |
|---|---|
| `unshare -rn` network namespace with loopback only | Even a misconfigured SDK has no route to real AWS |
| `env -i` before anything starts | The machine's real AWS keys are not visible to the test process |
| `--telemetry off` | The emulator sends usage telemetry by default; I turned it off |
| Emulator package from the public download host | No AWS account or sign-in |
| boto3 1.44.2, `max_attempts=1` | Errors surface on the first try instead of being retried away |

**Takeaway:** the setup is the kind a CI runner can copy, and the cost was zero. The emulator's account ID is all zeros; the raw files replace it with the placeholder `123456789012`.

"Expected on AWS" in the tables below comes from AWS documentation, not from a live account. Running the same checks on real AWS costs money, so I didn't.

## Where the emulator matched AWS

| Check (what the test asserts) | Expected on AWS (docs) | Emulator v1.0.343 |
|---|---|---|
| DynamoDB: second insert of the same key with `attribute_not_exists(pk)` | `ConditionalCheckFailedException` | `ConditionalCheckFailedException`, HTTP 400 |
| S3: second create-only `PutObject` with `If-None-Match: *` | `PreconditionFailed`, HTTP 412 | `PreconditionFailed`, HTTP 412 |
| IAM: user whose own policy denies `s3:GetObject` reads the object | `AccessDenied` (explicit deny wins) | `AccessDenied`, HTTP 403, "with an explicit deny" |
| IAM: brand-new user with no policies reads an object | `AccessDenied` (no allow means deny) | `AccessDenied`, HTTP 403 |
| SQS: receive, receive again at once, receive after the 2 s visibility timeout | 1 message, 0 messages, 1 message | 1 message, 0 messages, 1 message |
| DynamoDB: `ConsistentRead=True` on a GSI query | `ValidationException` | `ValidationException`, "Consistent reads are not supported on global secondary indexes" |
| Bedrock Runtime: `Converse` with a model ID that doesn't exist | `ValidationException` | `ValidationException`, "The provided model identifier is invalid." |

**Takeaway:** the assertions most idempotency and locking code relies on, such as "the second writer loses" and "a hidden message stays hidden", behaved the way the AWS docs describe. Those tests are reasonable to run locally. The "conditionally claim the step in DynamoDB" pattern from [Durable Long-Running Jobs with Amazon Bedrock AgentCore](/blog/2026-08-01-durable-long-running-jobs-with-agentcore.html) is exactly this kind of test.

## Where a green test means nothing

### Bedrock returns a placeholder that looks like success

The `Converse` call, with a JSON-only prompt, came back as a normal response:

```json
{"text": "No language model runs in this emulator. anthropic.claude-sonnet-5-5 generated no text for this request. The request carried 1 message(s) and 11 input token(s).",
 "stopReason": "end_turn",
 "usage": {"inputTokens": 11, "outputTokens": 55, "totalTokens": 66}}
```

The reply is honest if a person reads it. A test doesn't read it. `stopReason` is `end_turn`, the text is non-empty, and the usage block has token counts. A check like `assert reply["text"]` or `assert usage["outputTokens"] > 0` passes. A check that parses the reply as JSON fails, which is the useful outcome.

**Who hits this:** anyone pointing an agent or LLM wrapper test suite at the emulator. **What to check:** every Bedrock test must assert on content the placeholder can't produce, or be marked as needing real Bedrock.

### A GSI that is always up to date

I wrote 200 items to a table with a GSI, and after each write I queried the GSI for that item at once.

| Run | GSI queries straight after a write (count) | Item found on the first try (count) |
|---|---|---|
| Emulator v1.0.343 | 200 | 200 |

**Takeaway:** the emulator's GSI behaves as if it were strongly consistent. The [DynamoDB docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html) say GSI reads are eventually consistent and don't support strongly consistent reads; the emulator even enforces the second half (the `ValidationException` above) while skipping the first. Code that writes and then immediately reads through a GSI will pass locally every time and can fail on AWS. I didn't measure how often it fails on AWS.

### AgentCore Runtime fails loudly

`InvokeAgentRuntime` on a runtime that was never created returned `NotImplemented` (HTTP 501, "scaffolded but not implemented"). AWS would return a not-found error. That is the case the announcement describes, and it's the good kind of gap: the test goes red instead of green.

## The release's own scores agree

Each release publishes per-service check results. For v1.0.343:

| Service | Checks passed (count) | Checks in total (count) | Passed (%) |
|---|---|---|---|
| DynamoDB | 1,464 | 2,142 | 68.3 |
| S3 | 1,946 | 2,845 | 68.4 |
| SQS | 1,098 | 1,536 | 71.5 |
| IAM | 747 | 1,238 | 60.3 |
| KMS | 395 | 510 | 77.5 |
| Lambda | 1,744 | 3,021 | 57.7 |
| Bedrock Runtime | 102 | 183 | 55.7 |
| AgentCore (data plane) | 32 | 100 | 32.0 |
| AgentCore (control plane) | 68 | 198 | 34.3 |

**Takeaway:** the core storage and queue services pass about two thirds to three quarters of their checks; the AI services pass half or less. Read "supported" as "supported per operation, release by release", and pin the emulator version in CI so a green run means the same thing next week.

## Security checks: the binary and the docs disagree

The [security page](https://docs.aws.amazon.com/emulator/latest/userguide/security.html) says:

> The emulator never denies a request signed with its own key. It doesn't check AWS KMS key policies or Amazon S3 bucket policies.

In v1.0.343 I saw the opposite on both counts:

| Check | What the security page says | Emulator v1.0.343 |
|---|---|---|
| Bucket policy denies `s3:GetObject` to everyone; read with the emulator's own key | Not checked; own key is never denied | `AccessDenied`, HTTP 403 |
| KMS key policy denies `kms:Decrypt` to an emulator-created user | Key policies not checked | `AccessDeniedException` |

**Takeaway:** a security test can be green or red locally for reasons that have nothing to do with AWS, and the behavior can change between releases. The page's advice stands: test IAM, resource policies, and key policies on real AWS.

## The one setting that can send a test to real AWS

The security page also warns that if `AWS_ENDPOINT_URL` isn't set, the SDK calls AWS with whatever credentials it finds. I checked what boto3 does with the variable removed:

| Environment | Endpoint boto3 used | Result inside the no-network namespace |
|---|---|---|
| `AWS_ENDPOINT_URL` unset, `AWS_CONFIG_FILE` still pointing at the emulator's generated config | `https://127.0.0.1:9297` | Call succeeded against the emulator |
| Both unset | `https://sts.us-east-1.amazonaws.com` | `EndpointConnectionError` (the namespace has no route out) |

**Takeaway:** the emulator's config file is a second safety net, but only if your CI sets `AWS_CONFIG_FILE`. On a runner with network access and real credentials in the environment, the second row would have reached AWS. Unset real credentials and set both variables in the same script that runs the tests.

## What I'd move, and what I wouldn't

| Test type | Move to the emulator? | Why |
|---|---|---|
| Idempotency, conditional writes, create-only puts | Yes | Matched AWS docs in every check above |
| Queue retry and visibility timing | Yes | Matched |
| Input validation and error handling | Yes, per operation | Matched where checked; confirm the operation isn't a 501 |
| Read-after-write through a GSI | No | Emulator never shows the lag AWS documents |
| Anything calling Bedrock models | No | Placeholder reply passes weak assertions |
| AgentCore Runtime invocation | No | 501 today |
| IAM, bucket policy, key policy | No | Docs say don't, and the binary disagrees with the docs |

**Takeaway:** the emulator is a good fit for the boring, deterministic half of an AWS test suite. Keep a small real-AWS stage for consistency, model calls, and security.

## Limits

- One release, one machine, boto3 only. Other SDKs and later releases can differ.
- "Expected on AWS" is from documentation. I didn't run these checks on a real account, because that costs money.
- 13 checks is a sample, not a fidelity audit. The release scores are the broader view.
