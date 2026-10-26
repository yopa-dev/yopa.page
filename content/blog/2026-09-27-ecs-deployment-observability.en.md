---
title: "ECS Deployments Can Say 'Completed' With Nothing Running: The New Console Timeline, and the Pipeline Check That Misses It"
date: 2026-09-27T09:00:00-04:00
author: Yoonsoo Park
description: "Amazon ECS now shows a live deployment timeline in the console. It is a real improvement for anyone who deploys by hand. But in my test environment a rollout reported success three different ways while zero tasks were running, and the common pipeline check, aws ecs wait services-stable, passed on a service with no tasks at all. I reproduced that. Here is the new console view, what it cannot show you, and a check that actually fails."
categories:
  - AWS
  - DevOps
tags:
  - Amazon ECS
  - fargate
  - deployment
  - observability
  - circuit-breaker
aliases:
  - /blog/2026-09-23-ecs-deployment-observability.html
---

Deploying a service on ECS (Amazon Elastic Container Service) has always been a two-tool job. You start the rollout with `aws ecs update-service`, then you go somewhere else to find out if it worked: `describe-services` for the deployment state, the service event log, CloudWatch Logs for the task, and CloudTrail if none of those explain it. You keep the state machine in your head and poll it.

This month ECS started drawing that state machine for you, in the console. That part is good news, and I will cover it first.

Then the part the console cannot fix. In my own test environment, a small app of two Fargate services, a rollout reported success three different ways while nothing was running. And when I went back to check the command most pipelines use to wait for a deploy, `aws ecs wait services-stable`, it passed on a service with zero tasks. I reproduced that on purpose, and the result is below.

## What the new Deployments tab gives you

Open any ECS service in the console and go to the **Deployments** tab. For services on the native deployment types (rolling, linear, canary, and blue/green), it shows the deployment as it happens:

- **Phase, service events, and task progress** on one timeline, live. You can see whether it is starting new tasks, waiting on a lifecycle hook, or sitting in bake time, without reading JSON.
- **How much traffic has moved** from the old revision to the new one. For canary and blue/green, that is the number you care about during the rollout.
- **Health signals in one place**: the circuit breaker (the ECS feature that stops a deployment after too many task failures and can roll it back), with live failure counts against its threshold; alarm state; container and load balancer health checks; and lifecycle hooks.
- **Failed tasks with the reason and a link into CloudTrail**, so "why did it die" and "who changed what" are one click away.

It costs nothing extra and is in all commercial Regions and GovCloud.

| Question | Before | Now |
|----------|--------|-----|
| Which phase is it in? | Read `deployments[].rolloutState` | The timeline shows the phase |
| How much traffic has moved? | Work it out from load balancer stats | Shown in the timeline |
| Did the circuit breaker trip? | See `rolloutState = FAILED` and guess | Circuit breaker status with thresholds |
| Did the alarm fire? | Check CloudWatch separately | Alarm state on the timeline |
| Why did the task die? | CloudWatch Logs, then CloudTrail | Failed tasks with the reason and CloudTrail links |

The old loop looked like this, three query shapes where `status` and `rolloutState` are easy to mix up under pressure:

```bash
aws ecs update-service --cluster my-cluster --service my-service --force-new-deployment
aws ecs describe-services --cluster my-cluster --services my-service \
  --query 'services[0].deployments[].[status,rolloutState,desiredCount,runningCount,failedTasks]'
aws ecs describe-services --cluster my-cluster --services my-service \
  --query 'services[0].events[:10].[createdAt,message]'
```

Keep the scope in mind. This is **deployment** observability: what happened to one rollout. It does not replace your metrics, traces, or logs. It is not an API you can query later, and it is not a deployment history.

- Pro: if you deploy by hand, it replaces three polling commands and a lot of guessing.
- Con: it lives only in the console. Nothing in a pipeline can read it, and it only covers the native deployment types. Services still on the CodeDeploy controller show nothing.

## My setup, and why it is the worst case

My test app is two Fargate services, each running one small task (0.5 vCPU, 1 GB). They are Slack agents that connect out over Socket Mode, so there is no load balancer and no HTTP port. The health check is a no-op, and each service allows the old task to stop before the new one starts:

```ts
circuitBreaker: { enable: true, rollback: true },
minHealthyPercent: 0,   // one task; there is no room for two
maxHealthyPercent: 100,
healthCheck: { command: ["CMD-SHELL", "true"] }, // no port to check
```

With one task and `minHealthyPercent: 0`, the rollout **is** the outage window. And with a health check that always passes, the circuit breaker is the only thing that can notice a crash loop. So this setup leans entirely on the deployment machinery. That is exactly why the next part hurt.

## Three ways a rollout reported success with nothing running

These all happened on one evening in my test environment. The times are local.

**1. The infrastructure code reset the task count on every deploy.**

My CDK code had `desiredCount: 0`. I had put it there so the services would ship "dark", and I scaled them up by hand afterwards. CloudFormation writes the value from the code back on every deploy, so every release quietly scaled both services back to zero:

```
18:45:00  task definition registered
18:45:06  has stopped 1 running tasks
18:46:25  deployment completed
18:46:25  has reached a steady state      <- desiredCount 0, runningCount 0
```

Every line is true. The deployment did complete. The service is in a steady state. It is also down, and it stays down until someone notices. The console timeline shows this as a clean finish, because by its own definition it is one.

The fix is in the code: put the real count in the source, and take a service down by changing it there. A count you set by hand undoes itself on the next release.

It got worse before it got better. My fix for this was later undone by accident, when a stale copy of the file was copied over the fixed one and committed with a message that only described the other change in it. Nothing in the pipeline noticed, because nothing in the pipeline checked the count.

**2. The error message named the wrong cause.**

After I scaled the services back up, ECS could not place a task:

```
18:59:51  was unable to place a task. The reason for failure is
          Capacity is unavailable at this time. Please try again later
          or in a different availability zone.
```

"Capacity is unavailable" sends you to check your task size and subnets. So before touching anything, I built a control: a test that removes my changes from the picture. A plain `busybox` task, no volumes, no secrets, same size, same subnets and security group, **in a different cluster**. I ran it once in each AZ (availability zone, one of the separate data centers in a Region):

| Test | Result |
| --- | --- |
| `busybox` task, other cluster, AZ a | `RunTask -> ServerException: Internal Error` |
| `busybox` task, other cluster, AZ b | same |
| A request that is invalid on purpose | `InvalidParameterException`, a normal validation error |
| Create a network interface directly in each AZ | succeeded |
| Fargate vCPU quota | 4,000, with 1.5 in use |

The invalid request mattered most. ECS answered it with a correct validation error, so the API was up and reading requests. Only the step that places a valid task was failing, with a server error, in both AZs, for a task that had nothing to do with my change. The message the service showed me was a guess about the cause, not a diagnosis. I could not check the AWS Health dashboard for my account, because that needs a Business support plan.

**3. Silence was not recovery, and not failure either.**

```
18:59:51  unable to place a task
          ... 46 minutes of nothing ...
19:45:52  deployment failed: tasks failed to start
19:48:50  has started 1 tasks
19:52:00  deployment completed / steady state
```

For 46 minutes the service posted no new events. ECS backs off after repeated placement failures, and it also stops repeating the same event, so a service stuck in backoff looks exactly like a quiet, healthy one. The 19:45 line is the circuit breaker doing its job, and it was the first honest signal in three quarters of an hour.

One more thing I did not expect: **the service scheduler and the `RunTask` API are not the same path.** My other service placed its task at 19:33, while my own `run-task` probes at 19:32 and 19:34 were still getting `ServerException`. I had set up a watcher that waited for `run-task` to succeed before nudging the services. It would have waited forever while the scheduler was already placing tasks. A synthetic probe built on `run-task` can be red while your services are fine, and, less comfortably, green while they are not.

## The pipeline check that passes on zero tasks

Most pipelines wait for an ECS deploy like this:

```bash
aws ecs wait services-stable --cluster my-cluster --services my-service
```

I went and read what that waiter actually checks. In botocore, the library behind the AWS CLI, its success condition is:

```
length(services[?!(length(deployments) == `1` && runningCount == desiredCount)]) == `0`
```

In words: one deployment, and the running count equals the desired count. **0 equals 0.** So I built exactly that case in a test account and ran it: one ECS service with `desiredCount: 0`, deployed with CDK, then a forced new deployment, then the waiter. No task ever ran.

```
10:37:31.9  force-new-deployment   -> new PRIMARY deployment, IN_PROGRESS, desired 0, running 0
10:38:34    services-stable        -> exit 0 after 63 s
            describe-services      -> desired 0, running 0, PRIMARY still IN_PROGRESS
10:38:59    ECS event              -> deployment completed, steady state
```

The waiter said "stable" with zero tasks running, and it said so **25 seconds before ECS itself called the deployment complete.** A pipeline gated on this would have gone green on the exact failure from Finding 1.

The same condition also passes after a circuit breaker rollback. Once ECS rolls back, there is one deployment again (the old revision) and its counts match. I read that from the waiter's definition and did not trigger a rollback, so treat that one as from the source, not executed.

Here is the check I use now. It fails unless the new revision really finished with the number of tasks I meant to run:

```bash
#!/usr/bin/env bash
# usage: check-rollout.sh <cluster> <service> <expected-task-def-arn> <expected-count>
set -euo pipefail
cluster=$1 service=$2 want_td=$3 want_n=$4
read -r state td running desired < <(aws ecs describe-services --cluster "$cluster" --services "$service" \
  --query 'services[0].deployments[?status==`PRIMARY`] | [0].[rolloutState, taskDefinition, runningCount, desiredCount]' \
  --output text)
fail=0
[ "$state" = "COMPLETED" ]   || { echo "FAIL: rolloutState is $state"; fail=1; }
[ "$td" = "$want_td" ]       || { echo "FAIL: running ${td##*/}, expected ${want_td##*/} (rolled back?)"; fail=1; }
[ "$desired" -ge "$want_n" ] || { echo "FAIL: desiredCount is $desired (did the IaC reset it?)"; fail=1; }
[ "$running" -ge "$want_n" ] || { echo "FAIL: runningCount is $running"; fail=1; }
exit "$fail"
```

On the same test service, right after the waiter passed:

```
primary: rolloutState=IN_PROGRESS running=0 desired=0 taskDef=...:1
FAIL: rolloutState is IN_PROGRESS, not COMPLETED
FAIL: desiredCount is 0, expected at least 1 (IaC reset it?)
FAIL: runningCount is 0, expected at least 1
exit 1
```

Run it after the waiter, or in a loop with a timeout of your own. The waiter tells you the service stopped moving. It does not tell you the service is doing what you meant.

The test setup, the check, and the raw output are in [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/main/2026-09-27-ecs-deployment-observability).

## Pitfalls

- **"Steady state" is not "serving".** A deployment can complete, reach steady state, and leave `runningCount` at zero. Check the count against the number you intended, not `rolloutState` alone.
- **`wait services-stable` passes on 0/0,** and after a rollback. Pair it with a check like the one above.
- **Don't scale a service by hand if your IaC also sets the count.** The next deploy puts the code's number back.
- **Treat the reason in a service event as a guess.** Before you change anything, run a control that removes your change: a plain task, somewhere unrelated.
- **Silence is not good news.** No new events can mean ECS is backing off, not that things are fine.
- **Don't build a health probe on `run-task`** and assume it tells you about your services. They took different paths in my test.
- **`minHealthyPercent: 0` gives you a gap whose length you don't control.** On a normal day mine is about a minute. That evening it was fifty minutes, and the deployment had reported success in under two.

## What to do

- **If you deploy by hand:** open the Deployments tab before you start guessing at `describe-services` output. The phase is right there.
- **If you deploy from a pipeline:** this launch changes nothing for you, because nothing in a pipeline can read the console. Check what your pipeline actually waits on. If it is `wait services-stable` alone, add a check on the primary deployment's state, its task definition, and the running count.
- **If your IaC sets `desiredCount`:** make it the real number, and change it in code.

For running a real service on ECS end to end, including version pinning, secrets, and rollback, see [Run n8n Queue Mode on AWS ECS with Recoverable Operations](/blog/2026-08-01-run-n8n-queue-mode-on-aws-ecs.html). For a single-task agent on Fargate, see [how I first deployed an AI agent to ECS Fargate](/blog/2026-05-23-deploy-hermes-ai-agent-aws-ecs-fargate-slack.html).

## References

- [AWS What's New: Amazon ECS real-time deployment observability](https://aws.amazon.com/about-aws/whats-new/2026/09/amazon-ecs-console-deployment-observability/)
- [Amazon ECS deployment circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)
- [Amazon ECS service deployment types](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-types.html)
- [`aws ecs wait services-stable`](https://docs.aws.amazon.com/cli/latest/reference/ecs/wait/services-stable.html), and its waiter definition in botocore (`botocore/data/ecs/2014-11-13/waiters-2.json`)
