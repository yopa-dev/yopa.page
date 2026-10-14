# yopa.page Newsletter Content Engine

Audience: Hermes agent and future yopa.page collaborators
Status: planning draft; no automation or sending approval implied
Owner: Yoonsoo Park
Created: 2026-08-09

## 1. Why this plan exists

yopa.page now has a bilingual monthly email subscription path, but a reliable
email requires a reliable editorial input loop. The goal is not to become a
general AI or AWS news publication. The goal is to turn a small number of
important changes into tested, durable engineering judgment.

The operating question is:

> Which AI or AWS change materially affects how Yoonsoo builds and operates a
> GenAI application, and what can be learned by testing it in a real system?

The newsletter should answer that question once per month. News discovery is
an upstream research activity, not the product readers receive.

## 2. Current yopa.page state

### Website and growth loop

- yopa.page is a bilingual Hugo engineering publication with English and Korean
  content.
- Article Atlas Growth MVP was deployed on 2026-08-09.
- The first Expedition is `safe-agent-operations`, with five bilingual stops.
- The visitor loop is:

  ```text
  useful article
  -> Expedition
  -> practical result
  -> optional yopa.page email subscription
  -> monthly return
  ```

- The first four-week growth evaluation is scheduled for 2026-09-06.
- Maker's Road, Workshop, App Garden, Presence, accounts, and other World Plan
  expansion remain gated during this measurement window.

### Email infrastructure

- beehiiv hosts separate English and Korean publications.
- Public subscription URLs:
  - English: `https://yopapage.beehiiv.com/`
  - Korean: `https://yopa-field-dispatch-ko.beehiiv.com/`
- Double opt-in, Smart Nudge, confirmation, welcome, unsubscribe, and language
  isolation have passed owner acceptance.
- Successful confirmations return to language-specific pages on yopa.page.
- Public-facing naming is now `yopa.page`; do not introduce `Field Dispatch` as
  the reader-facing brand.
- Current site promise: one useful email per month. It does not promise a fixed
  number of new posts.
- Sending remains an owner-final action. No agent may send or publish an email
  without explicit approval at the time of sending.

### Analytics and privacy

- GA receives coarse Expedition and CTA events plus anonymous confirmation-page
  views.
- Subscriber identities are not sent to GA.
- Agents must not query subscriber emails, custom fields, exports, or individual
  subscriber records.
- Aggregate baseline reports are private and ignored by Git.

### Existing editorial seed

- The repository contains more than 300 articles, including a recent body of
  AWS, Bedrock, AgentCore, agent security, deployment, cost, and operations
  material.
- Existing August English and Korean email drafts are under
  `docs/field-dispatch/`. They are references, not automatic send inputs, and
  still require editorial review and public-brand terminology cleanup.
- The strongest existing content pattern is already suitable for the email:
  notice an AWS change, reproduce it, apply it to a real GenAI system, document
  the boundary or corrected assumption, and publish the durable result.

## 3. Product decision

Do not increase output merely to fill a newsletter. The recommended monthly
unit is:

> One field-tested anchor article, supported by two or three signals that
> explain why the experiment mattered.

One strong article is sufficient for one monthly email. A second full article
is optional and should be published only when a second experiment independently
earns it.

The email is not:

- a list of ten AI headlines;
- an automated RSS digest;
- a paraphrase of other newsletters;
- a product-announcement recap without testing;
- a requirement to publish two weak posts every month;
- a machine-generated bilingual send.

## 4. Editorial promise

Each monthly email should help a working engineer answer four questions:

1. What changed?
2. Why might it affect a production GenAI application?
3. What did Yoonsoo actually test, build, operate, or compare?
4. What design decision changed, stayed the same, or remains unproven?

The durable value is judgment backed by evidence. Speed is secondary.

## 5. Content object model

Every candidate moves through three states.

### Signal

A release, model change, architecture claim, incident, research result, or
recurring discussion. A signal is private editorial input and is not yet a
publishable claim.

Minimum fields:

- title;
- original public URL;
- publisher and publication date;
- discovery source;
- relevance to the current GenAI application;
- claim requiring verification;
- smallest useful experiment;
- decision that might change;
- expiration or review date.

### Experiment

A bounded attempt to verify a selected signal in a real or representative
environment.

Minimum evidence:

- question and expected result;
- scope, cost ceiling, and stop condition;
- environment and versions;
- commands, configuration, or code needed to reproduce it;
- observed result;
- failure modes and operational boundaries;
- security, identity, cost, reliability, and rollback implications;
- evidence classification: documentation-derived, synthetic, local runtime,
  personal AWS runtime, or production runtime.

Never describe local fixtures or synthetic tests as company or production
evidence.

### Field note

A bilingual public article or article pair that converts the experiment into a
decision another engineer can reuse. It should outlive the news cycle and link
to primary sources.

## 6. Source strategy

### Tier 1: primary sources

Prefer these when verifying claims:

- AWS What's New and service release notes;
- AWS service documentation and public repositories;
- AWS Architecture, Security, Containers, and Machine Learning publications;
- official OpenAI, Anthropic, Google, and model-provider documentation;
- official SDK and framework repositories, changelogs, and issues;
- original research papers;
- security advisories and incident reports.

### Tier 2: discovery sources

Use selected newsletters, practitioners, conference talks, podcasts, and news
coverage to discover questions. They do not replace primary-source verification.

### Selection boundary

A popular announcement is not automatically relevant. Prefer signals connected
to:

- production GenAI applications;
- AI agents and coding agents;
- Bedrock, AgentCore, Lambda, ECS, Step Functions, and adjacent AWS systems;
- workload identity, delegated-user identity, authorization, and isolation;
- observability, cost attribution, durability, recovery, and deployment;
- a concrete system Yoonsoo is already building or operating.

## 7. Candidate scoring

Score each candidate before assigning experimentation time.

| Criterion | Score |
| --- | ---: |
| Direct relevance to a current GenAI system | 0-3 |
| Verifiable with a small bounded experiment | 0-2 |
| Could change an architecture or operating decision | 0-2 |
| Produces a reusable lesson for another engineer | 0-2 |
| Likely to remain useful after one month | 0-1 |

Only candidates scoring 7 or more should normally enter the experiment queue.
Editorial judgment may override the number, but the reason must be recorded.

## 8. Agent responsibilities

### Gemini Spark: private inbox scout

Gemini Spark may be used to inspect an owner-selected Gmail label and produce a
small weekly digest. Its role is collection and first-pass classification.

Allowed:

- inspect only the designated AI/AWS newsletter label;
- identify at most five candidates from the previous seven days;
- extract title, publisher, date, direct link, main claim, and relevance;
- cluster repeated themes across newsletters;
- note what is materially new compared with the previous digest;
- propose one minimal experiment per candidate;
- identify a reason to ignore a candidate.

Not allowed:

- send, forward, archive, delete, unsubscribe, or reply without owner approval;
- draft the final yopa.page article or email as if research were verified;
- copy newsletter prose into the repository;
- expose unrelated inbox contents;
- treat a newsletter summary as a primary source;
- automatically promote a candidate into the publication queue.

Spark is an early, access-dependent service. This workflow must continue to
work if Spark is unavailable. The fallback is a manually maintained list of
public links from the same designated inbox label.

Suggested weekly Spark instruction:

```text
Every Friday, review only emails received in the last seven days under my
AI/AWS newsletter label.

Select no more than five items relevant to production GenAI applications,
AI and coding agents, AWS Bedrock or AgentCore, identity, authorization,
isolation, observability, cost, reliability, recovery, and deployment.

For each item provide:
1. original title, publisher, date, and direct public link;
2. what is materially new;
3. why it may affect a GenAI application I currently build or operate;
4. the smallest experiment that could verify the claim;
5. which architecture or operating decision might change;
6. what still requires verification from a primary source;
7. one reason this item may be safe to ignore.

Do not write newsletter copy. Do not reuse source prose. Do not modify email,
calendar, Drive, or subscription state.
```

### Codex: verification and repository production

Codex is responsible for turning an owner-selected candidate into verifiable
work inside the authorized project scope.

Responsibilities:

- open the primary sources and verify dates, availability, limits, and claims;
- search the existing yopa.page corpus for duplication or required maintenance;
- design the smallest safe experiment and explicit evidence boundary;
- implement or execute approved experiments;
- preserve commands, tests, cost assumptions, and rollback notes;
- draft or revise the bilingual article pair;
- keep Korean prose native rather than literal translation;
- preserve original article history when maintaining older content;
- create the monthly email draft from approved public evidence;
- validate frontmatter, links, JavaScript, tests, and Hugo production output;
- never send through beehiiv and never query subscriber identity data.

### Hermes: editorial operations coordinator

Hermes should maintain the recurring operating loop, detect stalled work, and
prepare bounded handoffs. Hermes is not authorized to publish or send.

Responsibilities:

- prompt the owner once per week for the Spark digest or selected links;
- maintain a private candidate queue without copying source email bodies;
- apply the scoring rubric and surface the top two candidates;
- ask the owner to select zero or one primary monthly question;
- create a bounded experiment brief for Codex;
- track whether evidence, article, bilingual review, and email draft are ready;
- detect when the month has insufficient evidence and recommend a smaller
  issue rather than inventing content;
- prepare the owner approval checklist for article publication and email send;
- record missed cadence without automatically compensating with low-value work.

Hermes must treat owner silence as no approval. It must not broaden an
experiment, access a personal inbox, publish an article, or send an email merely
because a scheduled date arrives.

### Owner: thesis, evidence authority, and final publication

Only the owner may:

- choose the primary monthly question;
- approve access to the designated inbox label;
- decide which personal or AWS environment may be used;
- confirm that a claimed real-world result actually occurred;
- decide whether private, employer, or account-bound information is publishable;
- approve English and Korean editorial voice;
- publish the article;
- perform the final beehiiv review and send.

## 9. Monthly operating cadence

### Weekly intake: 20 minutes

Every Friday:

1. Spark or the owner produces at most five candidate links.
2. Hermes normalizes only public metadata and verification questions.
3. Codex checks primary-source availability and corpus duplication.
4. Hermes scores candidates and presents no more than two.
5. The owner selects zero or one for experimentation.

Choosing zero is valid. A weak week should not create work merely to preserve
activity.

### Week 1: choose the question

Deliverables:

- one-sentence reader problem;
- one-sentence expected practical conclusion;
- selected primary sources;
- minimal experiment;
- cost and time ceiling;
- explicit evidence class;
- abort and rollback conditions.

Gate: the candidate must score at least 7 or have an owner-recorded exception.

### Week 2: run the experiment

Deliverables:

- reproducible evidence;
- result and counterexample;
- cost, security, identity, reliability, and operational implications;
- decision: adopt, adapt, reject, or keep investigating.

Gate: if the result cannot support a durable lesson, stop the full article and
retain only a private experiment note.

### Week 3: publish the anchor article

Recommended structure:

1. the real problem;
2. what the announcement or common advice claims;
3. the previous yopa.page approach;
4. experiment design;
5. observed result;
6. production boundaries and failure modes;
7. the decision that changed or survived;
8. when readers should and should not use the approach;
9. primary sources and evidence classification.

The English and Korean versions must share facts and evidence, but each should
read naturally in its language.

### Week 4: prepare the monthly email

The monthly email should be shorter than the anchor article and should not
repeat it section by section.

Recommended structure:

```text
Subject: a practical decision, not a product name
Preheader: what was tested and why it matters

1. This month's conclusion
   2-4 sentences stating the decision.

2. What changed
   The AI/AWS signal that triggered the work, linked to a primary source.

3. What I tested
   The experiment and its evidence boundary.

4. What I changed or kept
   The architecture or operating decision.

5. Read the field note
   One anchor yopa.page article.

6. Two signals I am watching
   Short annotations, not copied summaries.

7. What I did not verify
   One explicit uncertainty or rejected claim.

8. Next month's question
   One concrete investigation, with no promise that the answer is known.
```

Target length:

- 500-900 English words;
- a natural Korean edition with equivalent substance, not a sentence-level
  translation;
- one primary anchor link;
- at most three external signal links;
- no more than one primary CTA.

## 10. Monthly email production procedure

1. Hermes checks that the selected article is public and the final URL works.
2. Codex creates English and Korean editorial drafts under
   `docs/field-dispatch/YYYY-MM-en.md` and `YYYY-MM-ko.md` unless the directory
   is renamed in a later terminology cleanup.
3. Codex verifies every external claim against a primary source and checks every
   link.
4. Codex confirms the two versions have the same factual claims, evidence
   limits, and unsubscribe expectations.
5. The owner rewrites personal judgment and voice where necessary.
6. The owner approves subject, preheader, sender identity, preview, links, and
   language-specific audience in beehiiv.
7. The owner sends a test email to an owner-controlled address.
8. The owner checks desktop and mobile rendering, all links, and unsubscribe.
9. The owner performs the final send. Agents do not click the final send action.
10. Hermes records only send date, language, public links, and completion state.
    It does not store subscriber or recipient data.

## 11. Definition of ready for an article

An article is ready only when:

- the claim is tied to a current primary source;
- the experiment evidence is reproducible or its limitation is explicit;
- account, employer, customer, and credential data are absent;
- cost and security implications are addressed when relevant;
- the conclusion states when not to use the approach;
- English and Korean facts match;
- frontmatter and Hugo validation pass;
- the owner approves publication.

## 12. Definition of ready for an email

An email is ready only when:

- it contains one clear practical conclusion;
- the anchor article is already public;
- external news is context, not copied content;
- all claims have primary-source links;
- unverified claims are labelled or omitted;
- the English edition targets only the English publication;
- the Korean edition targets only the Korean publication;
- subject and preheader are reviewed in both languages;
- a test email has passed;
- the owner explicitly approves final sending.

## 13. Privacy, copyright, and operational boundaries

- Do not copy full newsletter bodies into a repository, agent task, log, or
  knowledge note.
- Do not reproduce distinctive source prose. Extract facts and independently
  express the verified conclusion.
- Cite the original public source. A newsletter may be credited as discovery
  context when appropriate, but it does not replace the primary source.
- Do not bypass paywalls or republish paid/private material.
- Keep Gmail access limited to an owner-selected label where the product allows
  it. Review Gemini connected-app settings before activation.
- Do not allow inbox automation to archive, delete, unsubscribe, reply, or send.
- Do not store credentials, subscriber data, private analytics output, or
  account identifiers in this plan.
- Do not automate the final beehiiv send.
- Do not state that an AWS feature was production-validated when evidence came
  from documentation, a fixture, or a personal test environment.

## 14. Phase plan

### Phase 0: two-week dry run

No email is sent because of this phase.

Deliverables:

- two weekly Spark or manual digests;
- no more than ten total candidates;
- normalized candidate metadata without source email bodies;
- scoring results;
- one selected experiment brief;
- one primary-source verification pass.

Gate:

- at least one candidate is specific and testable;
- links resolve directly to source material;
- the digest reduces attention rather than creating another large reading list;
- no private inbox content enters Git or agent memory.

### Phase 1: first evidence-backed issue

Deliverables:

- one bounded experiment;
- one anchor bilingual article or an existing article with a material verified
  update;
- one English and one Korean monthly email draft;
- owner test sends;
- owner final send.

Gate:

- the issue can be summarized as a changed or surviving decision;
- newsletter production adds no more than two hours beyond article work;
- the email remains useful with only one anchor article;
- no automated send or subscriber-data access occurs.

### Phase 2: two-month repeatability check

Run the loop for two consecutive months before increasing cadence.

Evaluate:

- candidates reviewed per month;
- candidates promoted to experiments;
- experiments producing publishable evidence;
- anchor articles published;
- time spent producing the email after the article;
- missed sends;
- clicks to the anchor article and Expedition using aggregate analytics;
- owner assessment of whether the process improved or drained the writing loop.

Gate to consider a second monthly article:

- two consecutive monthly emails were sent;
- the first anchor article was completed without deadline-driven quality loss;
- a second independent experiment repeatedly reaches publishable evidence;
- total editorial work remains sustainable;
- the second article serves a distinct reader question.

If the gate fails, retain one anchor article and one monthly email. Do not add
generic news volume to compensate.

## 15. Initial issue hypothesis

The first issue does not need a new broad news roundup. A suitable starting
point is:

> What did building and operating a real agent system change about the boundary
> between an impressive prototype and a safe GenAI application?

Possible inputs:

- the deployed `safe-agent-operations` Expedition;
- recent AgentCore, Bedrock, identity, authorization, or observability changes;
- the Hermes AWS-to-Synology migration and its cost/recovery evidence;
- one current coding-agent change that affected the development workflow;
- one claim explicitly rejected or postponed after verification.

The first issue should prove the editorial loop, not prove that yopa.page can
cover the entire AI news cycle.

## 16. Decisions Hermes must not make implicitly

Hermes must stop and ask the owner before:

- granting or expanding inbox access;
- selecting an AWS account or incurring experiment cost;
- converting personal, employer, or account-bound evidence into public copy;
- publishing an article;
- creating or changing a beehiiv audience;
- sending a test or final email;
- increasing from one to two anchor articles per month;
- changing the public monthly promise;
- implementing a new backend, scraper, database, or automation service.

## 17. Immediate next actions

1. Owner creates or confirms a dedicated Gmail label for selected AI/AWS
   newsletters.
2. Owner decides whether Gemini Spark may read only that selected label.
3. Hermes runs a two-week dry coordination cycle without publishing or sending.
4. Codex creates a minimal private candidate-ledger format only after the owner
   approves where it should live.
5. Owner selects the first monthly question from no more than two candidates.
6. Codex prepares the experiment brief and evidence plan.
7. After evidence exists, Codex drafts the bilingual anchor article and monthly
   email.
8. Owner reviews and performs all publication and send actions.

The durable target is not “two posts per month.” It is:

> Every month, choose one question worth testing, publish at least one strong
> evidence-backed field note, and send one useful yopa.page email.
