---
title: "AWS Vector Databases for RAG — A 2026 Architectural Decision Guide"
date: 2025-05-25T02:30:00-04:00
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "Choosing a vector store on AWS is no longer a five-way decision. With S3 Vectors added to OpenSearch, pgvector, Neptune Analytics, Bedrock Knowledge Bases, and Kendra, the real question is which tier of the cost/latency curve your workload lives on. Here's an updated decision framework."
categories:
  - AWS
  - Machine Learning
  - RAG
tags:
  - AWS
  - RAG
  - Vector Search
  - Amazon Bedrock
  - Amazon S3 Vectors
  - Amazon OpenSearch Service
---

> Choosing a vector store on AWS used to be a five-way decision. With **Amazon S3 Vectors** in the picture, it's now better framed as a question of *which tier of the cost/latency curve your workload belongs to*. This is an updated decision framework — what each option is good at, when it wins, and how they increasingly combine instead of compete.

> **Update note (2026):** This post was first written in May 2025. I've since reworked it to add S3 Vectors, mark the services that have graduated from preview to general availability, and cut the date-stamped claims that aged badly. If you read the original five-service version, the biggest change is that "pick one database" is now mostly the wrong question.

> **Review note (2026-10-21):** On August 5, 2026, AWS announced [general availability of native vector search in Amazon DynamoDB](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-dynamodb-vector-search/), shortly after this guide's August review. It now appears as its own row and section below: vectors stored on the operational table. The other options are unchanged.

## The mental model: a cost/latency tier, not a beauty contest

Most "which vector DB should I use" guides line up services side by side as if you pick one and commit. In practice the AWS-native options now sort cleanly onto a **cost vs. latency curve**:

| Tier | When it fits | AWS option |
|------|-------------|------------|
| **Hot / real-time** | High QPS, sub-50ms p99, always-on | OpenSearch Service |
| **Warm / transactional** | Vectors next to relational data, ACID | Aurora / RDS PostgreSQL + pgvector |
| **Operational table** | Vectors next to key-value items you already keep in DynamoDB | DynamoDB vector search |
| **Cold / cost-first** | Billions of vectors, infrequent or batch queries | **S3 Vectors** |
| **Managed / fastest-to-ship** | You want RAG, not a database | Bedrock Knowledge Bases |
| **Graph-aware** | Relationships matter as much as similarity | Neptune Analytics (GraphRAG) |
| **Turnkey enterprise search** | Connectors + access control, zero vector expertise | Kendra GenAI Index |

The interesting shift since 2025 is that the top and bottom of this table now **tier together**: you keep hot vectors in OpenSearch and spill the long tail into S3 Vectors, instead of paying memory prices for cold data. More on that below.

## Amazon S3 Vectors — the cost floor (the big addition)

This is the service that didn't exist when I first wrote this guide, and it changes the economics enough to deserve top billing.

S3 Vectors is the first object store with **native vector storage and query** — you create vector indexes inside S3 and query them through a dedicated API, with no cluster to provision. AWS positions it as reducing the cost of uploading, storing, and querying vectors **by up to 90%** versus running an always-on vector database.

**Key facts:**

- **Scale:** up to **2 billion vectors per index**, 10,000 indexes per vector bucket — into the trillions of vectors per bucket.
- **Latency:** warm queries land around **~100ms** (sub-second), not the single-digit milliseconds of an in-memory engine. This is the tradeoff.
- **Consistency:** strong consistency — a query always sees your most recently written vectors.
- **No infrastructure:** pay-for-what-you-use, zero provisioning.

**Where it fits:** large, long-lived vector datasets that are queried infrequently or in batch — agent long-term memory, archival semantic search, "search everything we've ever ingested" corpora. It is explicitly *not* the choice for high-QPS real-time serving.

**The integration that matters:** S3 Vectors is natively wired into **Bedrock Knowledge Bases** (so a KB can use S3 Vectors as its store and cut RAG cost), and into **OpenSearch Service** for a tiered strategy — hot vectors in OpenSearch for low latency, the cold bulk in S3 Vectors for cost. That tiering is the single most useful architectural pattern to come out of this update.

## Amazon OpenSearch Service — the scale and latency champion

OpenSearch remains the answer when you need **high QPS at sub-second (often single-digit-ms) latency** over very large vector counts. It's the most operationally flexible option and the most proven at billion-scale.

**Strengths:**

- Multiple engines (FAISS, Lucene, NMSLIB) with HNSW, IVF, and product quantization.
- Aggressive compression: binary quantization (~32x) and product quantization, plus disk-optimized ANN that cuts memory needs substantially.
- Serverless option with pay-per-OCU autoscaling for spiky traffic.
- Metadata filtering integrated with k-NN for multi-tenancy.

**Tradeoff:** it's a search cluster — you own the operational complexity and the memory bill. With S3 Vectors now available as a cold tier, the right move is increasingly *OpenSearch for the hot set, S3 Vectors for the rest* rather than sizing OpenSearch for your entire corpus.

## Aurora / RDS PostgreSQL + pgvector — the integration master

If your vectors live next to relational data, `pgvector` is the path of least resistance: vector search and ACID transactions in one engine, with familiar tooling.

**Strengths:**

- HNSW indexes, `halfvec` (50% memory reduction), sparse and binary vector types.
- Iterative index scans (0.8.x) that prevent over-filtering when you combine `WHERE` clauses with vector search.
- Graviton instances for better price/performance; Aurora Serverless v2 scales down for variable load.

**Tradeoff:** HNSW indexes want to live in memory, so instance sizing gets critical past a few million vectors. Best when relational + vector in one transactional store is worth more than peak vector throughput.

## Amazon DynamoDB vector search — vectors on the operational table

DynamoDB now stores embeddings as attributes on the items they describe. You create a vector index, run approximate nearest neighbor queries, choose the index partition key to scale, and filter on attributes to scope results. You generate the embeddings yourself, for example with a Bedrock model. It is serverless and pay-per-use like the rest of DynamoDB, and it is available in all commercial AWS Regions and AWS GovCloud (US) ([announcement](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-dynamodb-vector-search/)).

**When it wins:** the source of truth already lives in DynamoDB, so the vector index does not need a sync pipeline to a second store.

**Tradeoff:** it is vector *search*, not a RAG pipeline. Chunking, ingestion, and retrieve-and-generate are still yours to build. And if your data lives somewhere else, adding DynamoDB just to hold vectors brings the sync problem back. For a worked example and a longer when-it-replaces-a-vector-DB discussion, see [DynamoDB Now Does Vector Search](/blog/2026-08-06-dynamodb-native-vector-search.html). Measure recall on your own evaluation set before you move a workload.

## Amazon Bedrock Knowledge Bases — fastest path to RAG

If what you actually want is *retrieval-augmented generation* and not a vector database to operate, Bedrock Knowledge Bases is the managed front door: ingest → chunk → embed → retrieve → (optionally) generate, with the vector store abstracted away.

**What's matured since 2025:**

- It can sit on multiple backing stores — OpenSearch Serverless, Aurora pgvector, Neptune Analytics, and now **S3 Vectors** for cost-optimized RAG.
- Multimodal ingestion, structured-data (natural-language-to-SQL) retrieval, reranking, custom chunking, and built-in RAG evaluation have moved from "preview" toward standard features.
- GraphRAG (via Neptune Analytics) is available as a retrieval mode for relationship-rich corpora.

**Tradeoff:** less control over the retrieval internals. The migration path is the point: start on Bedrock KB to validate, drop to a self-managed store only when you've proven a specific need it can't meet.

## Amazon Neptune Analytics — the relationship expert

Neptune Analytics combines vector similarity with **graph traversal**, powering GraphRAG: multi-hop, relationship-aware retrieval that plain similarity search can't do. For knowledge graphs and densely interconnected documents it materially improves answer quality on questions that depend on *connections*, not just nearest neighbors.

**Tradeoff:** higher modeling complexity than pure vector search, and it only pays off when your data genuinely has rich relationships. If "find similar chunks" is enough, this is overkill.

## Amazon Kendra GenAI Index — turnkey enterprise search

Kendra delivers semantic enterprise search with **no vector expertise required**: managed connectors to enterprise sources, built-in document understanding, and native access control. The GenAI Index is tuned for RAG retrieval and can also feed Bedrock Knowledge Bases.

**Tradeoff:** the least flexible and not the cheapest at small scale, but the fastest time-to-value for "search our internal documents, respecting who's allowed to see what."

## Decision shortcuts

- **High QPS, real-time, large scale** → OpenSearch (spill cold vectors to S3 Vectors).
- **Billions of vectors, infrequent/batch queries, cost is the constraint** → S3 Vectors.
- **Vectors alongside relational data, need ACID** → Aurora/RDS pgvector.
- **Source of truth already in DynamoDB, want similar items plus their data in one query** → DynamoDB vector search.
- **You want RAG shipped this week, not a database to run** → Bedrock Knowledge Bases.
- **Answers depend on relationships, not just similarity** → Neptune Analytics (GraphRAG).
- **Enterprise document search with access control, no ML team** → Kendra GenAI Index.

## Anti-patterns to avoid

- **Sizing one hot store for your entire corpus.** This was the default in 2025 because there was no good cold tier. With S3 Vectors, paying in-memory prices for rarely-queried vectors is now a choice, not a necessity — tier instead.
- **Over-engineering the first deployment.** If Bedrock Knowledge Bases gets you to a working RAG demo, start there and migrate only when you've proven a concrete limitation.
- **Forcing every data type into one service.** Hybrid is normal: hot content in OpenSearch, cold bulk in S3 Vectors, relationships in Neptune, structured data in pgvector. Pick per data shape, not per dogma.
- **Skipping quantization.** Running full float32 vectors uncompressed wastes memory and money; binary/product quantization usually preserves quality at a fraction of the footprint.

Cheers! 🍺
