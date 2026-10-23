---
title: "DynamoDB Streams can resume from a timestamp now. Which timestamp do you store?"
date: 2026-10-23T09:00:00-04:00
author: Yoonsoo Park
description: "DynamoDB Streams added an AT_TIMESTAMP shard iterator on October 15. The record times it matches on are rounded down to the second, so the timestamp you save decides whether a restart re-reads records or silently drops them. I modeled six resume strategies over 200 crashes, checked which SDK versions and local tools support it, and wrote down what still needs a real table."
categories:
  - AWS
  - Architecture
tags:
  - amazon-dynamodb
  - dynamodb-streams
  - change-data-capture
  - reliability
  - idempotency
---

On October 15, DynamoDB Streams got a third way to start reading. Before, you had `TRIM_HORIZON` (the oldest record still kept, up to 24 hours back) and `LATEST` (only new records). Now the [What's New post](https://aws.amazon.com/about-aws/whats-new/2026/10/amazon-dynamodb-streams-timestamp-processing/) says you can "supply a timestamp and begin processing at the first record written at or after that time using the AT_TIMESTAMP shard iterator type."

That sounds like the end of the "replay 24 hours or lose the gap" choice. It mostly is. But the feature puts one question on your desk that the announcement doesn't answer: **if you save a timestamp so you can resume later, which value do you save?** One obvious answer re-reads a few records. Two other obvious answers drop records without any error.

**Short answer:**

- Save the `ApproximateCreationDateTime` of the last record you finished, exactly as the stream returned it, and resume from that value. You will re-read up to one second of records. In my model at 20 writes per second, that was 11.6 records on average and 28 at most. So your handler has to be idempotent.
- Don't add 1 ms and don't use your own clock. In the same model, both lost records in more than 9 of every 10 restarts.
- If you already store sequence numbers, keep doing that. `AFTER_SEQUENCE_NUMBER` was the only strategy with zero loss and zero duplicates. `AT_TIMESTAMP` is for starting a new consumer, rebuilding a projection, or replaying "everything since the incident at 14:05".
- A Lambda event source mapping on a DynamoDB stream can't use it. You need the KCL adapter 2.5.0 or later, or the raw Streams API.
- A timestamp older than the 24-hour window does not fail. It starts at the oldest record still kept, and the gap is silent. Check for that yourself.
- You can't test it locally. DynamoDB Local 3.3.2 returned `InternalFailure` for every `AT_TIMESTAMP` call I made. botocore older than 1.43.114 rejects the `Timestamp` parameter before sending anything.

Everything below ran on my machine with no AWS calls. The resume-strategy numbers come from a model of the documented rules, not from the service. The part that needs a real table is written up as an owner-run experiment at the end, with its cost.

## What the docs actually promise

Two sentences decide this. The [`GetShardIterator` API reference](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_streams_GetShardIterator.html) says the timestamp has "precision in milliseconds" and:

> The iterator points to the first stream record whose ApproximateCreationDateTime is at or after the specified timestamp.

The [`StreamRecord` reference](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_streams_StreamRecord.html) defines that field:

> The approximate date and time when the stream record was created, in UNIX epoch time format and rounded down to the closest second.

So you can ask for a millisecond, but every record carries a whole second. Every record written between 14:05:07.000 and 14:05:07.999 has the time 14:05:07. A request for 14:05:07.001 skips all of them, because none of them is "at or after" 14:05:07.001.

The same API page covers both edges. If the timestamp is "older than the current trim horizon, the iterator points to the oldest untrimmed stream record," and if it "is in the future, the request returns a `ValidationException`." The [adapter guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.Timestamp.html) says the same thing about old timestamps, more bluntly: "It does not return an error."

## Six ways to resume, 200 crashes each

I wrote a [small model](https://github.com/ypark9/yopa-experiments/tree/experiment/dynamodb-streams-resume-at-timestamp-20261023/2026-10-23-dynamodb-streams-resume-at-timestamp) of those rules:

- **Writes:** one shard, one hour of Poisson writes at 20 per second (71,799 records). Each record's time is floored to the second.
- **Crashes:** the consumer crashes after a random record, stays down for 60 seconds, and comes back. I repeated that 200 times.
- **Strategies:** six ways to choose where to resume. For each one, I counted records never processed ("lost") and records processed twice ("dup").

| Resume from | Restarts with loss | Mean lost | Max lost | Restarts with dups | Mean dup | Max dup |
|---|---|---|---|---|---|---|
| `LATEST` | 200 / 200 | 1,194 | 1,308 | 0 | 0 | 0 |
| `TRIM_HORIZON` | 0 | 0 | 0 | 200 / 200 | 34,119 | 67,888 |
| `AT_TIMESTAMP`, last record's time as returned | **0** | **0** | **0** | 200 / 200 | **11.6** | **28** |
| `AT_TIMESTAMP`, last record's time + 1 ms | 187 / 200 | 9.9 | 28 | 0 | 0 | 0 |
| `AT_TIMESTAMP`, your clock when you checkpointed | 191 / 200 | 10.5 | 28 | 0 | 0 | 0 |
| `AFTER_SEQUENCE_NUMBER` | 0 | 0 | 0 | 0 | 0 | 0 |

How to read it:

- **`LATEST`** loses everything written while you were down: 60 seconds × 20 writes ≈ 1,200 records.
- **`TRIM_HORIZON`** loses nothing but replays everything kept. In the model that is up to one hour. On a real stream it is up to 24 hours.
- **The last record's time, as returned,** re-reads the records from that second that you had already processed. The duplicate count is bounded by how many writes land in one second.
- **"+1 ms" and "my clock"** both land after the floored second, so they skip the records from that second that came after your last one. One crash in the model shows it: the last processed record was the 13th of 24 records in its second. Resuming at its time re-reads 12 records. Resuming 1 ms later skips the other 11.

The "+1 ms" version is the tempting one, because it looks like "start after the one I already did." It is the one that loses data, and the loss doesn't depend on crash timing or bad luck. It comes straight from the second-floor rule. It also doesn't show up in testing unless your test writes several records within one second.

## What I could check without an AWS account

**SDK support is version-scoped.** I installed two botocore versions and used the botocore Stubber, so nothing went on the wire:

```text
botocore 1.43.113: ParamValidationError: Unknown parameter in input: "Timestamp",
                   must be one of: StreamArn, ShardId, ShardIteratorType, SequenceNumber
botocore 1.43.118: accepted (stubbed, nothing sent)
```

I compared the bundled `dynamodbstreams` service models in each wheel. 1.43.114, uploaded to PyPI on October 14 (UTC), is the first one with both `AT_TIMESTAMP` and `Timestamp`. If your Lambda layer or container pins an older boto3, the call fails in your own process before it reaches AWS.

**DynamoDB Local can't stand in for the service here.** I ran [DynamoDB Local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html) 3.3.2 (released October 14) on 127.0.0.1 and wrote 12 items in two bursts. `TRIM_HORIZON` returned all 12. Every `AT_TIMESTAMP` call failed with `InternalFailure` ("The request processing has failed because of an unknown error"), including the 1970 and one-hour-in-the-future cases that should behave differently. That covered the last record's time, +1 ms, the client write time, 1970, the future and a missing `Timestamp`.

Two more things showed up:

- botocore retried each failure four times, which made the probe slow. Set `max_attempts` to 1 for local probes.
- DynamoDB Local stamped all 12 records with the same `ApproximateCreationDateTime`: the start of the minute, not the second. Writes about four seconds apart got the same time.

So a local test of your resume logic would be wrong twice: the call fails, and the timestamps are coarser than production.

## Where it fits, and where it doesn't

| Situation | Start position |
|---|---|
| Normal restart of an existing consumer | your stored sequence number (`AFTER_SEQUENCE_NUMBER`), as before |
| New consumer that should only see changes since a deploy or a cutover | `AT_TIMESTAMP` = the cutover time, minus a little for clock skew |
| Rebuild a projection or cache for "the last 3 hours" | `AT_TIMESTAMP` = now − 3 h, with an idempotent writer |
| Replay after an incident, from a known time | `AT_TIMESTAMP` = incident start, rounded down to the second |
| Lambda trigger on the table | not available. The [`CreateEventSourceMapping` reference](https://docs.aws.amazon.com/lambda/latest/api/API_CreateEventSourceMapping.html) says "AT_TIMESTAMP is supported only for Amazon Kinesis streams, Amazon DocumentDB, Amazon MSK, and self-managed Apache Kafka." |
| KCL application with an existing lease table | stop it first. See below. |

The KCL caveat is easy to trip on. The [adapter guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.Timestamp.html) says not to change the timestamp, or switch between `AT_TIMESTAMP`, `TRIM_HORIZON` and `LATEST`, in a running application with state in the lease table. Shards with stored checkpoints "continue from those checkpoints". The rest pick up the new setting, so "the application can therefore process different shards from different starting positions." Its fix: stop every worker, then either delete the lease table or start under a new application name.

## A resume helper that fails loudly

The gap you can't see is the dangerous one, so make the edges raise. This is pure Python with no AWS calls. It decides the timestamp and refuses the two cases the service handles silently or late:

```python
import time

RETENTION_S = 24 * 3600

def resume_timestamp(last_approx: float, now: float | None = None,
                     margin_s: float = 600) -> float:
    """last_approx: ApproximateCreationDateTime of the last record you fully
    processed, as the stream returned it (epoch seconds)."""
    now = time.time() if now is None else now
    if last_approx > now:
        raise ValueError("checkpoint is in the future: clock skew or a bad value")
    if now - last_approx > RETENTION_S - margin_s:
        raise RuntimeError(
            "checkpoint is near or past the 24 h window; AT_TIMESTAMP would "
            "start at the trim horizon and leave a silent gap. Rebuild instead.")
    return last_approx   # not + 0.001, not your own clock
```

Pair it with a dedupe on `SequenceNumber` for the first second after resume. Better still, make the writes idempotent, so replaying a second is harmless by design. The 10-minute margin is my choice. Records are trimmed on the service's schedule, not yours, so don't plan to resume right at the 24-hour edge.

## Owner-run experiment (not yet run)

The model encodes my reading of the docs. The things that need a real stream are:

- whether the service matches on the floored second the way the model assumes
- whether "+1 ms" really skips the rest of the second
- what the future-timestamp error looks like

I have not run this. The results below are blank until someone does.

**Estimated cost:**

- **What it creates:** one on-demand table with a `KEYS_ONLY` stream that exists for a few minutes, 12 tiny writes, and fewer than 100 stream reads.
- **List prices, us-east-1 (2026-10-23), from the public price data behind the [DynamoDB pricing page](https://aws.amazon.com/dynamodb/pricing/on-demand/):**
  - $0.625 per million write request units
  - $0.02 per 100,000 stream read request units
  - the first 2.5 million stream reads each month are free
- **Rough total:** well under $0.01. Storage for a few KB over a few minutes rounds to zero. This is an estimate, not a billing guarantee. Check Cost Explorer the next day.

**Steps:**

1. Check which account and role you are using. This is read-only and free:
   `aws sts get-caller-identity --query Arn --output text`
2. Get the code and an SDK new enough:
   `git clone https://github.com/ypark9/yopa-experiments && cd yopa-experiments && git checkout experiment/dynamodb-streams-resume-at-timestamp-20261023 && cd 2026-10-23-dynamodb-streams-resume-at-timestamp`
   `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
3. Run it. It refuses to start without the flag. It creates a table named `yopa-at-timestamp-<random>`, so it can't touch an existing table. It sets retries to 1 and deletes the table in a `finally` block:
   `AWS_REGION=us-east-1 python owner_run.py --i-understand-this-uses-my-aws-account`
4. Expected observations, if the docs hold:
   - `approx_has_fraction` is `false`
   - `resume_at_last_seen` returns item 3 and every record after it, including any earlier items stamped with the same second
   - `resume_at_last_seen_plus_1ms` starts at the first item stamped with a later second
   - `AT_TIMESTAMP_1970` returns all 12
   - `AT_TIMESTAMP_future_plus_1h` returns `ValidationException`

**Teardown and cost-stop checks:**

- The script prints `"teardown": "table deleted"`. If it prints `DELETE FAILED`, delete the table by hand:
  `aws dynamodb delete-table --table-name <name from output>`
- Confirm that nothing is left:
  `aws dynamodb list-tables --query "TableNames[?starts_with(@, 'yopa-at-timestamp-')]"` should print `[]`.
- Deleting the table also removes its stream. Nothing else is created.

**Results:** _not yet run._

## What I did not measure

- **No real stream.** Every resume-strategy number comes from a model of the documented rules.
- **Multiple shards and shard splits.** The model has one shard. On a real table you resume per shard, and a split adds child shards that also need a start position.
- **Write rate.** The duplicate bound depends on it. At 20 writes per second it was at most 28 records. At 2,000 writes per second, plan for thousands.
- **Throughput and cost of replay.** The KCL adapter path and the cost of replaying hours of records at scale.

If you use DynamoDB Streams for a [vector index sync](/blog/2026-08-06-dynamodb-native-vector-search.html) or any other projection, the useful change is that a rebuild no longer has to start 24 hours back. Store the record's own time, accept one second of duplicates, and make the edges loud.
