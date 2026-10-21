---
title: How to Check if Google Analytics is Working
date: 2024-01-25
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "Ensure your Google Analytics is accurately tracking your site's traffic. Learn to identify and fix duplicate tracking codes with Google Tag Assistant."
categories:
  - Web Development
tags:
  - Google Analytics
  - Web Tracking
  - Tag Assistant
  - Observability
---

![oni-google-ish...](images/oni-google.webp)

> **Review note (2026-10-21):** This walkthrough originally found a Universal Analytics (UA) container next to a GA4 one. Universal Analytics stopped processing data on July 1, 2023, and properties were shut down and deleted from the week of July 1, 2024 ([Google Analytics Help](https://support.google.com/analytics/answer/11583528)). GA4 with the Google tag is the only setup left. The duplicate check below now looks for what can still go wrong: the same GA4 tag configured twice.

Ensuring that your Google Analytics is set up correctly is crucial for accurately tracking your website's traffic. While the Realtime report in Google Analytics provides immediate data about active users on your site, it doesn't guarantee the absence of issues like duplicate tracking codes, which can distort your data significantly.

To accurately check your website for such discrepancies, Google offers a powerful tool: the **Google Tag Assistant**. This tool is not just a basic checker; it's an essential instrument for anyone serious about accurate data analytics.

## How to Use Google Tag Assistant Tool

Google Tag Assistant allows you to identify and fix issues such as duplicate tracking codes, ensuring that your data reflects actual user behavior. Here's how you can use this tool to verify your Google Analytics setup:

1. **Access Tag Assistant**: Start by visiting [tagassistant.google.com](https://tagassistant.google.com).

2. **Choose Your Assessment Method**: You have two options: assess a domain directly on the site or use the Tag Assistant Companion browser extension in Chrome for a more integrated experience.

![Add the Domain](images/Tag-assistant.webp) 3. **Add Your Domain**: Click the 'Add domain' button to start the assessment process for your specific domain.

![Connect the Domain](images/Connect-domain.webp) 4. **Connect Your Domain**: After clicking 'Connect', your website will open in a new window. Don't close this window; it's crucial for the assessment process.

![Tag Assistant Tab](images/Tag-Assistant-tab.webp) 5. **Review Installed Tags**: Return to the Tag Assistant tab to review the tags installed on your site. This is where you can see if you have any duplicate or incorrect implementations. When this post was first written, the example site still loaded a legacy UA container next to the **Google Analytics 4** one. That specific problem is gone, because UA no longer collects data. If you still find a `UA-` tag, it is dead code to remove. Check that it is not the tag your GA4 property reuses as a connected site tag before you do (see below).

## What a duplicate looks like with GA4

The common duplicate today is one GA4 measurement ID (`G-…`) configured twice on a page. A typical cause is a hard-coded `gtag.js` snippet in the site template plus a Google tag in Google Tag Manager. Google recommends [having only one Google tag instance on a page](https://support.google.com/analytics/answer/9973999), and notes that if you use Tag Manager, [you don't need to add gtag.js snippets to your site](https://developers.google.com/analytics/devguides/collection/ga4/tag-options). A tag configured twice can produce duplicate data or mixed settings.

Check it without changing anything first:

1. In Tag Assistant, open one page. Check whether the same `G-` ID is listed more than once, and whether a single page load sends two `page_view` events.
2. Search your site template and your Tag Manager container for the same measurement ID.

If you find two, remove one implementation. Usually you keep Tag Manager and delete the hard-coded snippet. Then repeat the Tag Assistant check and confirm one `page_view` per page load. If you cannot remove one right away, the GA4 web data stream's Google tag settings include **Ignore duplicate instances of on-page configuration**, which tells the tag to ignore repeated on-page config commands.

By following these steps, you're not just checking if Google Analytics is working; you're ensuring that it's working correctly. The Tag Assistant tool is a definitive way to verify your setup, giving you confidence in the data you're using to make important business decisions.

## Wrapping it up 👏

Accurate data is the cornerstone of effective web analytics. By utilizing the Google Tag Assistant, you're taking a crucial step towards ensuring the integrity of your data. Remember, in the world of analytics, precision matters. Don't just track; track correctly. Cheers to data-driven success!

Cheers! 🍺
