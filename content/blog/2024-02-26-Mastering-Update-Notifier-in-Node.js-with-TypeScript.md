---
title: Update Notifications in Node.js with TypeScript
date: 2024-02-26
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "Explore how to integrate and leverage the update-notifier package in your TypeScript-based Node.js applications, including advanced usage and detailed examples."
categories:
  - Node.js
  - TypeScript
  - npm packages
tags:
  - Node.js
  - JavaScript
  - Package Management
  - TypeScript
---

![TypeScript with Update-Notifier](images/oni-red-flag.webp)

> **Review note (2026-10-21):** The original `tsconfig.json` used `"target": "es5"`. TypeScript 6.0 deprecated it and TypeScript 7.0 removed it (`TS5108`). The config is now ESM (`"module": "nodenext"`), which matches `update-notifier` being an ES module. JSON imports now use `with { type: "json" }`. The install step now adds `@types/update-notifier`, because `update-notifier` 7.3.1 ships no type declarations.

Keeping your Node.js application up-to-date is crucial for security, performance, and feature enhancements. The `update-notifier` npm package, when used with TypeScript, provides a powerful yet straightforward way to notify users of your application about new updates. This blog delves into the integration of `update-notifier` within a TypeScript environment, covering both basic and advanced usages with detailed code examples.

## Introduction to Update-Notifier with TypeScript

`update-notifier` is a handy tool for Node.js applications to check for available updates and notify users, ensuring they are always using the latest version. Integrating it with TypeScript adds type safety and enhances code readability and maintainability.

### Setting Up Your TypeScript Project

Before diving into `update-notifier`, ensure your TypeScript environment is set up. `update-notifier` is an ES module, so mark the project as ESM in `package.json`:

```json
{
  "type": "module"
}
```

Then configure `tsconfig.json` for Node.js ESM:

```json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "nodenext",
    "strict": true,
    "resolveJsonModule": true,
    "types": ["node"]
  }
}
```

The `resolveJsonModule` option in `compilerOptions` allows TypeScript to import JSON modules, such as your `package.json` file. This is crucial for `update-notifier` to access the current version and package name. Under `"module": "nodenext"`, an ESM JSON import needs an import attribute: `import pkg from "./package.json" with { type: "json" };`. The `types` entry is needed because TypeScript 6.0 and later default `types` to `[]`.

Do not use `"target": "es5"`. TypeScript 7.0 rejects it with `TS5108: Option 'target=ES5' has been removed`, and current Node.js LTS releases run ES2022 natively.

### Installing Update-Notifier

Current `update-notifier` releases are ESM-only and do not bundle TypeScript declarations. Confirm the package version and Node module mode before using the examples. Notifications should be disabled in CI and non-interactive output, and should never block the command.

To add `update-notifier` to your project, run:

```bash
npm install update-notifier
npm install --save-dev @types/update-notifier @types/node
```

The second command installs the TypeScript type definitions for `update-notifier`, allowing for type checking and IntelliSense in your IDE. Run `npx tsc --noEmit` once before adding notification logic. If it reports `TS7016: Could not find a declaration file for module 'update-notifier'`, the type package is missing.

## Basic Usage in TypeScript

After ensuring your `tsconfig.json` is properly configured to import JSON modules, you can now easily import your `package.json`:

```typescript
import updateNotifier from "update-notifier";
import pkg from "./package.json" with { type: "json" };

const notifier = updateNotifier({
  pkg,
  updateCheckInterval: 1000 * 60 * 60 * 24,
});

if (notifier.update) {
  notifier.notify();
}
```

This script will check for updates once a day and notify the user when there's a new version available.

## Advanced Usage Examples

### Prompting Users to Update

You can prompt users interactively to update their application using `inquirer` alongside `update-notifier`. Here's a TypeScript example:

```typescript
import updateNotifier from "update-notifier";
import inquirer from "inquirer";
import pkg from "./package.json" with { type: "json" };
import { execSync } from "child_process";

const notifier = updateNotifier({ pkg });

if (notifier.update) {
  inquirer
    .prompt([
      {
        type: "confirm",
        name: "update",
        message: `Update available: ${notifier.update.latest}. Do you want to update now?`,
        default: false,
      },
    ])
    .then((answers: any) => {
      if (answers.update) {
        execSync(`npm install -g ${pkg.name}`, { stdio: "inherit" });
      }
    });
}
```

### Custom Notifications Based on Update Type

You can customize the notification message based on the update type (major, minor, patch) using TypeScript's enum and type checking features:

```typescript
import updateNotifier, { type UpdateInfo } from "update-notifier";
import pkg from "./package.json" with { type: "json" };

const notifier = updateNotifier({ pkg });

if (notifier.update) {
  let message: string = "";
  const update: UpdateInfo = notifier.update;

  switch (update.type) {
    case "major":
      message =
        "A new major version is available. Updating is highly recommended!";
      break;
    case "minor":
      message =
        "A new minor version is available. Update to access new features.";
      break;
    case "patch":
      message =
        "A new patch version is available. Update to improve stability.";
      break;
  }

  notifier.notify({ message });
}
```

### Logging Update Details

For more detailed logging, especially useful in debugging or maintaining logs, you can utilize TypeScript to ensure structured and type-safe logging:

```typescript
import updateNotifier from "update-notifier";
import pkg from "./package.json" with { type: "json" };

const notifier = updateNotifier({ pkg });

if (notifier.update) {
  console.log(`Update available: ${notifier.update.latest}`);
  console.log(`Current version: ${pkg.version}`);
  console.log(`Update type: ${notifier.update.type}`);
}
```

## Conclusion

Update notifications should be a non-blocking convenience. Respect CI and non-interactive environments, provide an opt-out where appropriate, and do not make network availability a requirement for the command to succeed.
