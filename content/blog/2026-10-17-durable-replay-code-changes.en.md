---
title: "Will a Paused Lambda Durable Function Survive Your Next Deploy? 23 Replay Cases, Measured Locally"
date: 2026-10-17T09:00:00-04:00
author: Yoonsoo Park
description: "The Lambda Durable Execution SDK for Go went GA this week with a local test runner and a linter that catches code that could break a workflow when it resumes. I ran 23 cases through both, 60 trials each, with no AWS account. 10 of the 13 code changes broke a paused execution, 3 of them silently, and the linter flagged none of the 13. Here is what each tool caught and what to pin at deploy time."
categories:
  - AWS
  - Architecture
tags:
  - lambda
  - Durable Workflows
  - Go
  - Reliability
  - measured
---

On 2026-10-15 AWS [made the Lambda Durable Execution SDK for Go generally available](https://aws.amazon.com/about-aws/whats-new/2026/10/aws-lambda-durable-go-sdk-support/). A durable function is a Lambda function that saves the result of each step as it runs. When it waits, for a timer or for a person, the invocation ends. Later Lambda invokes it again, and the SDK **replays** the handler from the top: each finished step returns its saved result instead of running again, and the handler continues from the first step that has no saved result.

The announcement says you can test whole workflows locally with the `durabletest` package, "without requiring network access or AWS credentials, and use the durablelint analyzer to catch code that could break a workflow when it resumes." The Lambda docs add a warning: an execution started on `$LATEST` that is paused while you update the code [resumes on the new code](https://docs.aws.amazon.com/lambda/latest/dg/durable-invoking.html), which can lead to "non-determinism errors or silent failures."

That leaves the questions I would have before shipping one of these: which mistakes fail loudly, which fail silently, and which of the two tools catches which? So I wrote 23 small cases, most of them meant to break replay and a few meant to be safe, and ran each one 60 times through the SDK's own local runner. Short answer:

1. **Code changes while an execution is paused: 10 of 13 broke it.** Six changes to the names, order or types of finished operations failed replay with `NonDeterministicExecutionError`, every time. Changing a finished step's result type failed with a `SerdesError`. Three changes **succeeded with a wrong answer**: renaming a JSON tag, adding a field, and changing the logic inside a finished step.
2. **durablelint flagged 0 of those 13.** It checks one version of your code. It cannot see a change between two versions, and it does not claim to.
3. **Bugs inside one version: durablelint flagged 6 of 8.** It missed a clock read inside a helper function and a map whose keys were copied into an unsorted slice. Three of the 8 bugs never failed at all; they only produced inconsistent data. Three failed at random, between about half and three quarters of the time.
4. **One bug cannot show up locally at all.** `ctx.RequestID()` returned an empty string in both invocations under the local runner, so the case the linter warns about passed 60 of 60 trials.

This extends two earlier posts that stayed at the design level: [durable long-running jobs with AgentCore](/blog/2026-08-01-durable-long-running-jobs-with-agentcore.html), which argues that a durable orchestrator should own the business process, and [Step Functions × AgentCore](/blog/2026-06-04-step-functions-agentcore-async-pipelines.html), which lists a durable function callback as one pattern for long work. Neither says what happens when the orchestrator's own code changes under a paused execution.

## What replay actually compares

Each operation (step, wait, child context) gets an ID derived from its position in the handler. On replay the SDK takes the saved record at that position and checks it against the operation the code is running now. Here is the check, from the SDK's `validation.go`, shortened:

```go
if op.opType != expectedType {
	return &NonDeterministicExecutionError{...}
}
if expectedSubType != "" && op.subType != expectedSubType {
	return &NonDeterministicExecutionError{...}
}
if op.name != expectedName {
	return &NonDeterministicExecutionError{...}
}
return nil
```

It compares the operation type (step or wait), the subtype, and the name you gave it. It does not compare the step's code, its result type, or anything computed between steps. So a change that shifts a type or a name at a saved position fails loudly, and a change that keeps them fails quietly or not at all.

## The setup

One Linux machine: Go 1.24.4, SDK v1.0.0 (commit `e8c24d2`), `durablelint` from the same commit. No AWS account, no credentials. The run script refuses to start if AWS credentials are visible and runs the harness inside a network namespace with no interfaces, so an AWS call would have failed instead of reaching AWS. **Cost: $0.**

The local runner keeps its saved records across calls, so one runner can play a whole execution. To deploy new code in the middle, I put a switch in front of two handlers:

```go
var version atomic.Int32
version.Store(1)
h := func(ctx durable.Context, e I) (O, error) {
	if version.Load() == 1 {
		return v1(ctx, e)
	}
	return v2(ctx, e)
}
r := durabletest.NewLocalRunner(durable.Handler[I, O](h))
first, err = r.Run(in) // one invocation: runs until the wait suspends it
...
version.Store(2)
final, err = r.RunUntilComplete(in)
```

`Run` does one invocation, which stops at a one-hour `durable.Wait`. Then the switch flips and `RunUntilComplete` finishes the same execution on the new code. I did not find a way in `durabletest` to load one execution's records into a runner for different code, so the switch is my stand-in for a deploy.

**Group A** replays the same code, which is what you still get after you pin a version. **Group B** starts on v1 and resumes on a changed v2, which is what an execution on `$LATEST` can see. The B workflow's v1 is four operations:

```text
validate → reserve (returns Reservation{ID: "R-42", Price: 100}) → wait "pause" 1h → charge
```

Each case ran 20 trials per process, in 3 separate processes: 60 trials. Each run ended in one of four ways: replay **failed loudly** with `NonDeterministicExecutionError`, it failed with **another error**, it **succeeded with a wrong result** (for Group B, a result different from a fresh execution of v2), or it **worked correctly**. I also recorded whether a **golden-signature test** would fail: the SDK's `durabletest.AssertGoldenSignature` saves the list of operations (type, subtype, name, status) from one run and fails when a later run differs.

## Group B: code changed while the execution was paused

| What changed in v2 while the execution was paused | What happened when it resumed on v2 | Would a golden-signature test fail? | Does durablelint flag it? |
|---|---|---|---|
| Rename a finished step | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | Yes | No |
| Swap two finished steps | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | Yes | No |
| Insert a step before the wait | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | Yes | No |
| Remove a finished step | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | Yes | No |
| Rename the wait it is paused on | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | Yes | No |
| Wrap a finished step in a child context, same name | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | Yes | No |
| Change a finished step's result type (struct to int) | Fails with another error: `SerdesError`, 60 of 60 | No | No |
| Rename a JSON tag in a finished step's result | **Succeeds with a wrong result, 60 of 60** | **No** | **No** |
| Add a field to a finished step's result | **Succeeds with a wrong result, 60 of 60** | **No** | **No** |
| Change the logic inside a finished step | **Succeeds with a wrong result, 60 of 60** | **No** | **No** |
| Insert a step after the wait | Works correctly, 60 of 60 | Yes (a false alarm) | No |
| Remove a step that has not run | Works correctly, 60 of 60 | Yes (a false alarm) | No |
| Change the wait's duration | Works correctly, 60 of 60 | No | No |
| No code change: flip an environment variable read between steps | Fails loudly: `NonDeterministicExecutionError`, 60 of 60 | No | No |

Takeaway: three of these changes resume without any error and give a wrong answer, and neither a golden-signature test nor durablelint catches them.[^cases]

Every Group B result was the same in all 60 trials. These are not flaky. They follow from the check above.

### The loud ones say exactly what happened

The error from renaming a finished step is a good error:

```text
durable: non-deterministic replay at step "c81e728d9d4c2f63": the checkpoint recorded
operation (type STEP, subtype "Step", name "reserve"), but the handler now runs
(type STEP, subtype "Step", name "reserve-stock"). The handler code changed between deployments.
```

Wrapping a finished step in a child context is the one I would have gotten wrong in review. Wrapping `reserve` in `durable.RunInChildContext(ctx, "reserve", ...)` keeps the name, so it looks harmless. But the type changes from `STEP` to `CONTEXT`, and replay fails.

Inserting a step before the wait versus after it is the rule for adding steps. A new step in the part that already ran shifts every position after it, and fails. The same step after the paused point runs normally, because no record exists there yet. So the rule is not "add steps at the end." It is "add steps after the furthest point any in-flight execution has reached," and you usually do not know where that is.

### The silent ones are about step results, not step order

A step's saved result is JSON. On replay the SDK decodes the old JSON into the new Go type. The JSON tag rename changed one struct tag:

```go
type Reservation struct {
	ID    string `json:"reservation_id"` // was "id"
	Price int    `json:"price"`
}
```

The saved record has `"id": "R-42"`, the new type looks for `reservation_id`, and Go's JSON decoder leaves the field empty without an error. The execution succeeded and returned `charged  100`, with the reservation ID missing (the double space is where `R-42` should be). A fresh run of the same v2 code returns `charged R-42 100`. Adding a field is the same mechanism from the other side: the new `Currency` field does not exist in the old record, so it decodes to `""`.

Changing the result type is the loud version: decoding a saved JSON object into an `int` fails with `json: cannot unmarshal object into Go value of type int`. Among result-type changes, the more drastic one is the safer one.

The logic change raised the price inside `reserve` from 100 to 120, a bug fix. The paused execution kept 100, because replay returns the saved result. That is intended, and it is what you want for a step that charged a card. But a fix to a finished step never reaches executions that already passed it. Changing the wait's duration is the same for waits: the paused execution kept its recorded 3600 seconds, while a fresh v2 execution recorded 86400.

### An environment variable, with no code change at all

This case has one handler. It reads `os.Getenv("FRAUD_CHECK")` between steps and runs an extra `fraud-check` step when it is `on`. I set it to `off` for the first invocation and `on` before the resume. Replay failed 60 of 60 times, like inserting a step before the wait. No code changed, so neither durablelint nor a golden signature can see it. Environment variables are part of a [published version's snapshot](https://docs.aws.amazon.com/lambda/latest/dg/configuration-versions.html), so pinning should freeze this one too (not tested on the service). A value read between steps from outside that snapshot, such as a parameter store or a flag service, would break replay by the same mechanism; I did not test those.

## Group A: the same code, replayed

Pinning a version keeps the code fixed. It does not make the code deterministic.

| Bug in the handler | Does durablelint flag it? | What happened on replay (60 trials) |
|---|---|---|
| `time.Now()` between steps, used as a key | Yes | **Succeeded with a wrong result, 60 of 60** |
| `rand.Uint64()` between steps, used as a key | Yes | **Succeeded with a wrong result, 60 of 60** |
| The same clock read, inside a helper with no `durable.Context` | **No** | **Succeeded with a wrong result, 60 of 60** |
| A random branch adds a step before the wait | Yes | Failed loudly 43 times, worked 17 times |
| `range` over a map, one step per key | Yes | Failed loudly 31 times, worked 29 times |
| Map keys copied to a slice without sorting, one step per key | **No** | Failed loudly 41 times, worked 19 times |
| Plain goroutines call `durable.Step` on the parent context | Yes | Failed on the first invocation, 60 of 60 |
| `ctx.RequestID()` between steps, used as a key | Yes | Worked, 60 of 60 (the local runner can't reproduce this bug) |
| Control: key made in a step, `durable.ExecutionStartTime`, sorted keys | No findings | Worked, 60 of 60 |

Takeaway: the three key bugs never fail, they just write inconsistent data, and durablelint misses two of the eight bugs, including one of those three.

### The worst bugs here never fail

The `time.Now()`, `rand.Uint64()` and helper-clock bugs make a key between steps and pass it to two steps on either side of the wait:

```go
key := time.Now().UnixNano() // outside any step
r, err := durable.Step(ctx, "reserve", func(durable.StepContext) (int64, error) { return key, nil })
...
if err := durable.Wait(ctx, "pause", time.Hour); err != nil { ... }
c, err := durable.Step(ctx, "charge", func(durable.StepContext) (int64, error) { return key, nil })
```

On replay, `reserve` returns the key saved in the first invocation, while the line above it computes a new one for `charge`. The two keys differed in all 180 trials across the three cases, and every execution succeeded. If those were idempotency keys for a payment API, the API could not tell the two calls belong together, and nothing in the execution history would look wrong.

The fix is the control: make the key inside a step so it is saved once, and use `durable.ExecutionStartTime(ctx)` for a timestamp. The control passed 60 of 60, with the same start time in both invocations.

### Where durablelint is blind, it says so

durablelint flagged the `time.Now()` and `rand.Uint64()` bugs at the right line, with a useful message:

```text
time.Now is nondeterministic and is called outside a step body; move it into a durable.Step or use durable.ExecutionStartTime
```

It missed the clock read inside a helper and the unsorted copy of map keys, and both gaps are written down in the rule's own description:

```text
Limitations: only functions that receive a durable.Context are analysed;
a helper without a Context parameter that reads the clock is not reported
even when the handler calls it between operations.
```

The map rule reports "a range statement over a map whose body creates durable operations." In the unsorted-copy bug the loop over the map only copies the keys into a slice:

```go
names := make([]string, 0, len(items))
for name := range items {
	names = append(names, name) // forgot sort.Strings(names)
}
for _, name := range names {
	durable.Step(ctx, "pack-"+name, ...)
}
```

The order is just as random as with the plain `range` over the map, and this version failed replay 41 times out of 60. But the loop that creates the steps ranges over a slice, so the rule does not fire. A clean lint run means "none of the patterns it knows," not "deterministic." On the control it reported nothing, so I saw no false positives.

### Random failures make bad tests

The random branch and the two map bugs fail only when a replay takes a different path than the first invocation. In one process the plain map `range` failed 5 of 20 trials, in another 14 of 20. A test that runs such a handler once will often pass, and a golden-signature test on these three is itself flaky: it failed in 22 to 47 of 60 trials.

The rate is not portable either. Every execution in my harness replayed twice (the `Run` then `RunUntilComplete` path took 3 invocations; I counted). On the service, one wait might mean one replay. Read these as "fails at random," not as a production rate.

### `ctx.RequestID()`: the local runner cannot show this one

durablelint warns that `Context.RequestID` "changes on every invocation of an execution." Under the local runner, `ctx.RequestID()` returned `""` in both invocations, so the key matched on both sides of the wait and the bug passed all 60 trials. The runner numbers its invocations (`local-request-1`, `local-request-2`), but that value does not reach the handler. For this bug, the linter is the only local check that works.

## What to pin at deploy time

**1. Invoke a published version or an alias, never `$LATEST`, for anything that can pause across a deploy.** The [docs](https://docs.aws.amazon.com/lambda/latest/dg/durable-invoking.html) say an execution is pinned to the version that started it and resumes on that version. If so, every row of the Group B table turns into "nothing happens," the environment-variable row included. That is documented behavior; I did not test it on the service. My inference from it: the version an execution started on has to stay available until that execution ends.

**2. Run durablelint in CI, plus two review rules for its blind spots.** It caught 6 of the 8 in-version bugs with no false positive on the control. For the two it missed: no clock, random, or ID calls in helpers that orchestration code calls between steps; and sort map keys before any loop that creates steps, even when the map loop only collects keys.

**3. If executions ever resume on new code, treat step result types as a stored format.** Pinning avoids this, because an old execution never decodes its records with new types. On `$LATEST`, a renamed tag or a new field gave a silently wrong value in my runs, and a changed type gave an error.

**4. And if they do resume on new code, test exactly that.** The test below starts an execution on a copy of the deployed handler, lets it pause, resumes it on the new handler, and compares the result with a fresh run of the new handler. The matrix harness makes the same comparison: across the 13 code changes it failed all 10 unsafe ones and passed the 3 safe ones. Each check took about 41 ms.

```go
func TestPausedExecutionResumesOnNewCode(t *testing.T) {
	order := Order("order-1")

	var deployed atomic.Bool
	deployed.Store(true)
	h := func(ctx durable.Context, in Order) (Receipt, error) {
		if deployed.Load() {
			return deployedHandler(ctx, in) // a copy of the code that is live now
		}
		return Handler(ctx, in) // the code you are about to ship
	}
	r := durabletest.NewLocalRunner(durable.Handler[Order, Receipt](h))

	first, err := r.Run(order) // one invocation: runs until the first wait suspends it
	if err != nil {
		t.Fatal(err)
	}
	if first.Status != durabletest.Pending {
		t.Fatalf("want the first invocation to suspend, got %s", first.Status)
	}

	deployed.Store(false)
	got, err := r.RunUntilComplete(order)
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != durabletest.Succeeded {
		t.Fatalf("resume on new code failed: %s: %s", got.Error.Type, got.Error.Message)
	}

	want, err := durabletest.NewLocalRunner(Handler).RunUntilComplete(order)
	if err != nil {
		t.Fatal(err)
	}
	if got.RawResult != want.RawResult {
		t.Fatalf("resumed result %s, fresh result %s", got.RawResult, want.RawResult)
	}
}
```

The test only reads and compares; it creates nothing. I ran this exact code against the step rename (failed with the rename error), the JSON tag rename (failed with `resumed result "charged  100", fresh result "charged R-42 100"`), and a step inserted after the wait (passed). Limits: it checks only the first wait, it needs a frozen copy of the deployed handler in your repo, and a failure is not always a bug. The price fix inside a finished step fails it because the paused execution keeps the old price, which may be what you want. Read the failure before "fixing" it.

A golden-signature test is cheaper, since it needs no copy of the old code. Among the 13 code changes it flagged 8: the 6 that failed with `NonDeterministicExecutionError`, plus 2 false alarms on safe changes (inserting a step after the wait, removing a step that has not run). It missed all 4 that change what a step returns (the result type, the JSON tag, the new field and the logic change), because it compares operation names, not values.

## What I did not test

- **The real Lambda service.** Everything here is the SDK's local runner. I did not test version pinning, aliases, how many times the service replays, what `ctx.RequestID()` returns on the service, or what happens to an execution after a `NonDeterministicExecutionError` there.
- Only steps, waits and one child context. No `Map`, `Parallel`, callbacks, chained invokes, or custom serializers.
- One wait per handler, so each test pauses at one point.
- Go only. The other durable SDKs have their own replay checks.

## References

- [AWS Lambda Durable Execution SDK for Go is now generally available](https://aws.amazon.com/about-aws/whats-new/2026/10/aws-lambda-durable-go-sdk-support/) (2026-10-15)
- [aws-durable-execution-sdk-go](https://github.com/aws/aws-durable-execution-sdk-go) (v1.0.0, Apache-2.0), including the [durablelint README](https://github.com/aws/aws-durable-execution-sdk-go/blob/v1.0.0/analysis/README.md)
- [Invoking Lambda durable functions](https://docs.aws.amazon.com/lambda/latest/dg/durable-invoking.html): qualified ARNs and `$LATEST`
- [Best practices for Lambda durable functions](https://docs.aws.amazon.com/lambda/latest/dg/durable-best-practices.html)
- [Manage Lambda function versions](https://docs.aws.amazon.com/lambda/latest/dg/configuration-versions.html): what a version snapshot includes
- Experiment code and raw output: [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/experiment/durable-replay-code-changes-20261017/2026-10-17-durable-replay-code-changes)

[^cases]: The experiment repo names these cases `B01` to `B14` (code changed between versions) and `A01` to `A09` (same code replayed). They only matter if you want to find a row's raw output there.
