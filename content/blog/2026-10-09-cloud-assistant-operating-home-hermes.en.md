---
title: "Letting a Cloud Assistant Operate My Home Hermes Agent: Three Walls I Hit in One Evening"
date: 2026-10-09T22:00:00-04:00
author: Yoonsoo Park
description: "I asked a cloud assistant (Grok Bot) to talk to and repair the Hermes Agent running on my Synology NAS. Its Slack messages were dropped as bot traffic, a single root-owned lock file put Hermes in a crash loop with no SSH available, and reaching Dockge over Tailscale needed a local port forward. Each wall comes with the symptom, the cause in the public Hermes source, the decision I made, and how I checked it."
categories:
  - DevOps
  - Agentic AI
  - Self-Hosting
tags:
  - Hermes Agent
  - Synology
  - Slack Bot
  - Self-Hosting
  - AI Agents
  - Security
---

In August I [moved Hermes Agent from ECS Fargate to my Synology NAS](/blog/2026-08-08-migrate-hermes-from-aws-to-synology.html). It has been answering Slack DMs from a Dockge stack since then. This week I tried the next step: let a cloud assistant, Grok Bot, operate it for me. Grok Bot runs on its own computer in the cloud. It can send Slack messages through a connector, and it can drive a browser. It has no SSH key to my NAS.

On 2026-10-09 that plan hit three walls in one evening:

1. **Slack.** Messages the assistant sent *as me* were silently ignored by Hermes, because Hermes classified them as bot traffic.
2. **Recovery.** Hermes went into a crash loop because of one root-owned lock file, and the only tool available was the Dockge web UI.
3. **Reach.** Dockge is only on my home network. Getting the assistant there through Tailscale needed a local port forward, and an expired node key got in the way first.

The short answer: all three are fixable without SSH and without opening anything to the Internet, but each fix is also a decision about how much the assistant is trusted. For Slack, allowlist your own user ID with `SLACK_API_HUMAN_USERS`, not `SLACK_ALLOW_BOTS`. For recovery, accept that Dockge access is root on the NAS, and give the assistant that knowingly. For reach, limit the assistant's Tailscale node to the one port it needs before you think about turning off key expiry.

## Wall 1: Hermes ignored messages I sent through the assistant

**Symptom.** When I typed a message in the Slack app, Hermes answered. When the assistant sent the same kind of message through its Slack connector, Hermes did nothing. It made no difference whether it was a channel mention or a DM. The connector posts with my own user token, so in Slack the message shows my name, with a small "Sent using …" footer that names the app.

**Cause.** Early in handling each Slack event, Hermes asks whether it came from a bot. This is the check, from the Slack adapter on the public `main` branch of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) as of 2026-10-09:

```python
def _event_declares_bot_sender(self, event: dict) -> bool:
    """Return True when the Slack event itself identifies a bot sender."""
    if event.get("bot_id") or event.get("bot_profile") or event.get("subtype") == "bot_message":
        return True
    profile = event.get("user_profile")
    if isinstance(profile, dict) and bool(profile.get("is_bot")):
        return True
    # App-originated events may lack bot_id/subtype but carry app_id and no client_msg_id
    # (humans have one) → bot-authored unless the user is in _slack_api_human_users
    # (classic bot posts have no ``user`` so never match).
    # Real human-authored messages normally carry client_msg_id, so treat the combination as
    # app/bot-authored (#35777).
    if event.get("app_id") and not event.get("client_msg_id"):
        return event.get("user") not in self._slack_api_human_users()
    return False
```

In plain words: the first two `if` blocks catch real bots, which Slack labels clearly. The last `if` is the one that caught me. When you type in a Slack client, the event carries a `client_msg_id`. When a program posts through the Slack Web API, even with a person's user token, the event carries the posting app's `app_id` and no `client_msg_id`. Hermes treats "has `app_id`, has no `client_msg_id`" as an app talking. That is a reasonable guess, and it is how Hermes avoids two bots answering each other forever. But it also means a message *I* sent through an assistant looks exactly like a bot.

The one way out of that last check is the list returned by `_slack_api_human_users()`. That list is filled from `platforms.slack.extra.api_human_users` in `config.yaml`, or from the `SLACK_API_HUMAN_USERS` environment variable.

**Decision.** The [Hermes Slack docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack) offer two settings that would let the message through, and they are not the same size:

| Setting | What gets through | What it costs |
| --- | --- | --- |
| `SLACK_API_HUMAN_USERS=U0XXXXXXX` | API posts whose `user` is in the list, which here means only me | You maintain a list of user IDs |
| `SLACK_ALLOW_BOTS=mentions` | Any bot or app message that @mentions Hermes | Every bot in the workspace can reach Hermes with a mention |

The cost of the second row is bigger than it looks. Hermes has a separate allowlist of humans, `SLACK_ALLOWED_USERS`. I expected it to still apply to bots. It does not. This is the authorization check in `gateway/authz_mixin.py` on the same branch:

```python
        # Bots admitted by {PLATFORM}_ALLOW_BOTS (scoped env → the routed adapter's YAML ``allow_bots`` →
        # none) bypass the human allowlist (Slack Workflow Builder posts arrive with user=None). The YAML
        # rung is what a secondary profile has: its config is never bridged into the process env.
        if getattr(source, "is_bot", False):
            allow_bots_var = _ALLOW_BOTS_ENV.get(source.platform)
            if allow_bots_var:
                extra = {}
                with contextlib.suppress(Exception):
                    extra = self._adapter_extra_for_source(source)
                mode = str(_extra_or_secret(extra, "allow_bots", allow_bots_var, "none")).lower().strip()
                if mode in {"mentions", "all"}:
                    return True
        return False
```

If the sender is a bot and `allow_bots` is `mentions` or `all`, this returns `True`, which means "authorized", without looking at the human allowlist. The Slack adapter still requires the bot's message to @mention Hermes in `mentions` mode, so it is not wide open. But any workflow or integration that someone in the workspace installs can start a Hermes turn by mentioning it. For an agent that can run tools on my NAS, that is too much.

`SLACK_API_HUMAN_USERS` goes the other way. It changes only the bot question, and only for the listed people. The docs say the normal checks, including `SLACK_ALLOWED_USERS` and mention gating, still apply to the sender after that. The docs also say there is deliberately no "trust this app ID" option, because a bot token posts with the same `user` plus `app_id` shape, so trusting an app would let its own bot posts in.

So I chose the narrow one. The change in the Compose `environment` was one line:

```yaml
    environment:
      SLACK_API_HUMAN_USERS: "U0XXXXXXX"   # my own Slack member ID
```

The tradeoff I accepted: anything that can post with my user token now counts as me to Hermes. That includes the assistant, which is the point, but also any other app I have authorized to post as me. My user token is now as sensitive as my Slack password from Hermes's point of view.

**Verification.** At 17:56 ET the assistant sent a test DM through the connector. Hermes added its 👀 reaction and answered. One more thing: in my setup, Hermes answers a DM in a thread under the message, not in the DM itself. If the assistant checks for a reply by reading only the latest DM messages, it will think Hermes said nothing. It has to read the thread.

## Wall 2: one root-owned file, a crash loop, and no SSH

**Symptom.** The `hermes` stack showed as exited in Dockge. The gateway started, died right away, was restarted by `restart: unless-stopped`, and repeated this until it stopped with `exited with code 1`. The error was:

```text
PermissionError: [Errno 13] Permission denied: '/opt/data/installs/<generation-id>/.install.lock'
install state is not writable by this user
```

**Cause.** Exactly one file was wrong. `.install.lock` was owned by root (`0:0`) and had been created at 16:51 ET. Every directory around it was owned by the Hermes UID:GID as expected. Hermes runs as an unprivileged `hermes` user, so it could not take its own lock.

I do not know for certain what created the file as root. The likely answer is a `hermes` command run inside the container as root. The Hermes image's own boot script says this kind of thing happens. This comment is from `docker/stage2-hook.sh` on the public `main` branch:

```sh
# Always reset ownership of $HERMES_HOME/profiles to hermes on every
# boot. Profile dirs and files can land owned by root when commands
# are invoked via `docker exec <container> hermes …` (which defaults
# to root unless `-u` is passed), and that breaks the cont-init
# reconciler (02-reconcile-profiles) which runs as hermes and walks
# the profiles dir.
```

So the image knows root-run commands leave root-owned files. Why did a restart not heal it? Because the boot script only repairs a fixed list of directories:

```sh
    for sub in cron sessions logs hooks memories skills skins plans workspace home profiles pairing platforms/pairing; do
        if [ -e "$HERMES_HOME/$sub" ] && tree_has_non_hermes_owner "$HERMES_HOME/$sub"; then
            chown_hermes_tree "$HERMES_HOME/$sub"
        fi
    done
```

In plain words: for each name in that list, if anything inside it is not owned by `hermes`, give the whole tree back to `hermes`. `installs` is not in the list. Separate blocks later in the script repair `profiles`, `cron`, and the pairing directories on every boot. Nothing repairs `installs`. So restarting the stack again and again could never fix this. A person or a script had to.

**Decision.** Normally I would SSH into the NAS and run one `chown`. The assistant could not, and I did not want to give it SSH for this. Dockge can do something that turns out to be just as strong: start any container you describe. So the fix was a throwaway stack.

What I actually ran was a single throwaway stack that listed `installs/`, ran `chown -R`, and listed it again, all in one go. It worked. Looking back, it is the wrong shape to copy: the container does not wait for anyone to read the "before" output, so a wrong path or a wrong UID is already applied by the time a person checks. If I did this again, I would split it into two stacks, a read-only check and a fix that touches only the one file.

**Stack 1, check only.** It mounts `installs/` read-only and stops with an error if the lock file you expect is not there:

```yaml
# Temporary Dockge stack "hermes-permcheck". Read-only. Delete it after one run.
services:
  permcheck:
    image: busybox
    user: "0:0"
    restart: "no"
    volumes:
      - type: bind
        source: /volume1/docker/hermes/data/installs
        target: /fix
        read_only: true
        bind:
          create_host_path: false
    command:
      - sh
      - -euc
      - |
        test -e /fix/<install-id>/.install.lock
        echo "--- not owned by hermes:"
        find /fix \( ! -user <hermes-uid> -o ! -group <hermes-gid> \) -exec ls -lnd {} \;
```

Three details matter here. `read_only: true` means this stack cannot change anything. `create_host_path: false` makes Docker refuse to start if the host path does not exist; with the short `- host:container` form, a typo in the path can quietly create a new empty directory, and an empty listing looks exactly like "nothing is wrong". And `sh -euc` stops at the first failing command, so a missing lock file ends the run with an error instead of a clean exit.

Read the log. Only if it names the one lock file you expected, move on.

**Stack 2, fix one file and prove it.**

```yaml
# Temporary Dockge stack "hermes-permfix". Delete it after one run.
services:
  permfix:
    image: busybox
    user: "0:0"
    restart: "no"
    volumes:
      - type: bind
        source: /volume1/docker/hermes/data/installs
        target: /fix
        bind:
          create_host_path: false
    command:
      - sh
      - -euc
      - |
        f=/fix/<install-id>/.install.lock
        test -e "$$f"
        chown <hermes-uid>:<hermes-gid> "$$f"
        test "$$(stat -c '%u:%g' "$$f")" = "<hermes-uid>:<hermes-gid>"
        echo "fixed: $$(ls -ln "$$f")"
```

The doubled `$$` is not a typo. Compose treats a single `$` as its own variable substitution before the shell ever sees it, so `$$` is how you pass a literal `$` through to `sh`.

It changes only that one file, not the whole tree. With `-e`, a failed `chown` stops the script and the stack exits with an error. Without it, a script like my original would still exit 0 as long as its last command succeeded. The last check reads the owner back and fails if it is not the Hermes user.

I have not run these two files. They are what I would use next time, not a record of what happened.

The steps:

1. Create and start `hermes-permcheck`. Its log should name exactly the lock file you expected, and nothing else.
2. Create and start `hermes-permfix`. It should exit 0 and print the file with the Hermes UID and GID. Any other exit code means stop and look.
3. In the `hermes` stack, press **Start** only. Do not edit or redeploy its Compose file. The fix was in the data, not the configuration.
4. Delete both temporary stacks.

Mounting only `installs/` was deliberate. A root container with the whole data directory mounted can read the Slack tokens and the OAuth state. These could only touch the directory that was broken, and the fix stack only one file in it.

**Verification.** At 17:52 ET the gateway was up, Slack Socket Mode was connected, and the gateway log had no `not writable` lines.

One warning about how I checked. The Dockge log panel for a stack can show old scrollback, so it can still show the crash after the crash is over. I read the current state from inside the container instead, with `tail /opt/data/logs/gateway.log`.

**Prevention.** Run Hermes commands in the container as the Hermes user, never as root:

```sh
docker exec -u hermes <container> hermes <command>
```

If you use a container shell from a web UI instead, run `id` first. If it says `uid=0`, anything you create with `hermes` from there can become the next lock file.

**The part I did not expect.** The fix worked because Dockge let the assistant start a container as `user: "0:0"` with a host directory mounted. That is not a bug in Dockge. It is what Dockge is for. But it means an assistant with Dockge access can run a root container against any NAS path Docker can mount, with or without SSH. "No SSH" felt like a safety boundary. It was not one.

## Wall 3: getting the assistant to Dockge

Dockge runs on the NAS at port 5002. It is reachable on my home LAN and nowhere else, which is what I want. The assistant's computer is in the cloud.

**What I did.** I joined the assistant's computer to my tailnet as its own node (call it `assistant-node`). The NAS was already on the tailnet (`nas-node`, with an address like `100.x.y.z`).

**First trap: the browser could not reach the tailnet.** The assistant's machine could reach `100.x.y.z`, but its browser sends traffic through an egress proxy, and that proxy has no route to tailnet addresses. The fix was a local forward on the assistant's machine, so the browser only ever talks to `localhost`:

```sh
socat TCP-LISTEN:5002,bind=127.0.0.1,fork,reuseaddr TCP:100.x.y.z:5002
```

In plain words: listen on port 5002 on the loopback address only, and copy each connection to port 5002 on the NAS's tailnet address. The browser opens `http://localhost:5002` and gets Dockge. Binding to `127.0.0.1` matters. Without it, anything else that can reach that machine could use the forward too.

**Second trap: an expired node key.** Separately, the NAS's own Tailscale node key had expired, and it needed a fresh login before the assistant could reach it. [Tailscale's key expiry docs](https://tailscale.com/kb/1028/key-expiry) say new tailnets default to 180 days, so a NAS that has been fine for months can drop off the tailnet on an ordinary evening. The obvious fix is to disable key expiry on the NAS and on the assistant's node. My notes say "consider it", and I have not done it yet.

**The security tradeoff, honestly.** Joining a cloud assistant's computer to a tailnet gives that computer whatever your tailnet policy allows. If you never edited the policy, Tailscale's default lets every device reach every other device. Then the assistant can reach the NAS's DSM login, SSH port, and anything else on the tailnet, not just Dockge. Disabling key expiry on top of that makes the access permanent until someone removes it by hand.

What I would do, in this order. These are recommendations. I have not applied or tested them:

- **Limit the assistant node to one port.** Put a [tag](https://tailscale.com/kb/1068/tags) on the assistant node and on the NAS, and in the [tailnet policy](https://tailscale.com/kb/1018/acls) allow the assistant tag only to `tcp:5002` on the NAS tag. If your policy still has the default allow-all rule, adding a narrow rule changes nothing. You have to replace the allow-all rule with rules for your own devices too.
- **Prefer tags over disabling expiry per device.** Tailscale's docs say a device that is tagged and authenticated for the first time gets key expiry disabled by default. That ties the long-lived access to a tag you can see in the policy, not to a toggle on one device page.
- **Treat Dockge as the real boundary.** Even limited to port 5002, the assistant can still start a root container, as Wall 2 showed. Port limits keep it off SSH and DSM. They do not make Dockge access small.
- **Keep the forward local and temporary.** Bind `socat` to `127.0.0.1`, and stop it when the session ends.

## Something changed since the migration post

In the August migration post I wrote that I did not use `latest` and that the image tag and digest were pinned. That is no longer true. The current Compose file uses `nousresearch/hermes-agent:latest`, and [What's Up Docker (WUD)](https://getwud.app/docs/configuration/triggers/docker-compose/) watches the digest of that tag. The stack's WUD labels also select a Docker Compose trigger, which can pull a new image and recreate the stack when a new `latest` appears.

Two caveats. A WUD label by itself does not prove updates happen: the trigger also has to be registered, not in dry-run mode, and able to reach the Compose file and the Docker socket. I have not confirmed a successful automatic update. And I do not think this evening's crash was caused by an update: the evidence points to a root-run command.

The risk is still real. An unattended image change can change how Hermes treats its data directory, and the recovery for that kind of break, as Wall 2 shows, needs someone with Dockge in a browser. With a pinned digest, a change happens when I choose. With `latest`, it can happen at 3 a.m. If you copy my setup, pick one on purpose. Pin the digest and update by hand when you can watch. Or use `latest` with WUD if you value fresh fixes more than a predictable night.

## What this is based on

- **One incident, on 2026-10-09.** Everything under "Symptom" and "Verification" comes from my own incident notes written that evening, with times in ET. I did not run a new experiment for this post. The thing being tested was my real setup, and repeating it would mean breaking it again.
- **Checked against public source.** I read `_event_declares_bot_sender`, `_slack_api_human_users`, the `allow_bots` authorization bypass, and the `stage2-hook.sh` ownership repair in the public Hermes repository on its `main` branch as of 2026-10-09 (commit `3eb7ed0`), and the setting names and safety notes in the Hermes Slack docs. That is newer code than whatever `latest` image my NAS was running that evening, so line-for-line details may differ from what actually ran.
- **Not verified.** My notes say `SLACK_API_HUMAN_USERS` needs Hermes v2026.9.7 or later. I could not confirm the release it first shipped in. The Hermes Slack docs also disagree with themselves about whether the environment variable or `config.yaml` wins when both set `allow_bots`. Set it in one place only.
- **Generalized for publishing.** Slack IDs, the tailnet address, node names, and the Hermes UID:GID are placeholders. The temporary Compose file is rebuilt from my notes, not copied from the live stack.

## What to do before you hand your agent to an assistant

1. **Send one test message through the assistant before you need it.** If Hermes ignores it, add your own member ID to `SLACK_API_HUMAN_USERS`. Do not reach for `SLACK_ALLOW_BOTS`, because it skips the human allowlist.
2. **Teach the assistant to read threads.** Hermes answers DMs in a thread.
3. **Never run `hermes` as root in the container.** Use `docker exec -u hermes`. If a root-owned file lands in `installs/`, a restart will not fix it.
4. **Write the Dockge fix down now.** A throwaway busybox stack that mounts only the broken directory is a good no-SSH repair. It is also proof that Dockge access is root access, so decide who has it.
5. **Limit the assistant's tailnet node to the Dockge port** before you disable key expiry, and know when your NAS key expires.
6. **Decide between `latest` and a pinned digest on purpose.**

## Related posts

- [Migrating Hermes from AWS ECS to Synology Without Losing Its Memory](/blog/2026-08-08-migrate-hermes-from-aws-to-synology.html): the setup this post operates, and the pinning rule it no longer follows.
- [How Much Does It Cost to Run Hermes Agent on AWS?](/blog/2026-08-08-hermes-aws-cost-breakdown.html): why Hermes moved to the NAS in the first place.
- [Deploy Your Own AI Agent to AWS](/blog/2026-05-23-deploy-hermes-ai-agent-aws-ecs-fargate-slack.html): the original ECS deployment and its Slack app setup.
- [Your Agent's Refusal Only Covers the Rules You Wrote Down](/blog/2026-09-26-where-should-agent-refusals-live.html): the same question from the other side, which checks should live in code rather than in trust.

## Sources

- Hermes Agent, [Slack setup and configuration](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack), including `allow_bots` and `api_human_users`. Read 2026-10-09.
- Hermes Agent source, [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), `main` at commit `3eb7ed0`: the Slack adapter, the gateway authorization mixin, and `docker/stage2-hook.sh`.
- Tailscale, [Key expiry](https://tailscale.com/kb/1028/key-expiry), [Tags](https://tailscale.com/kb/1068/tags), and [Access control](https://tailscale.com/kb/1018/acls).
- What's Up Docker, [Docker Compose trigger](https://getwud.app/docs/configuration/triggers/docker-compose/).
