---
title: Streamline Your TypeScript Projects with Advanced Path Mapping Techniques
date: 2023-04-24T01:25:00-04:00
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "NO MORE ../../../../../../../../hate/my/life"
categories:
  - TypeScript
tags:
  - TypeScript
  - JavaScript
  - Module Systems
---

> **Review note (2026-10-21):** TypeScript 6.0 deprecated `baseUrl` and TypeScript 7.0 removed it. The original example now fails with `TS5102: Option 'baseUrl' has been removed` and `TS5090: Non-relative paths are not allowed`. The `paths` entries below are now written relative to `tsconfig.json`, and there is a new section on Node.js subpath imports for code that has to resolve at runtime.

## Runtime resolution matters

TypeScript `paths` changes compiler resolution only; it does not rewrite emitted import specifiers or teach Node.js how to load an alias. Configure the runtime or bundler too, or use package `imports`/`exports` where appropriate. Verify the built output in the same environment that runs it.

If you're a TypeScript developer, you may have encountered the "Cannot find module" error when importing a module from a relative or absolute path. This can be frustrating, especially when dealing with a large codebase.

## Path Mapping

In TypeScript, **Path Mapping** is a feature that allows you to specify aliases for module paths. This can be helpful when working with a large codebase with multiple directories and files. Path Mapping helps to simplify the importation process by allowing you to use a custom alias instead of a relative or absolute path.

For example, instead of using:

```typescript
import { someModule } from "../../path/to/module";
```

You can use:

```typescript
import { someModule } from "@customAlias/module";
```

## Setting up Path Mapping

To use Path Mapping in TypeScript, you need to add a "paths" property in your `tsconfig.json` file.
Here's an example:

```json
{
  "compilerOptions": {
    "paths": {
      "@customAlias/*": ["./src/app/*"],
      "@anotherAlias/*": ["./another-dir/*"]
    }
  }
}
```

In this example, we've added two Path Mapping aliases: "@customAlias" and "@anotherAlias". The first alias maps to the `src/app` directory, and the second maps to `another-dir` next to `src`. Without `baseUrl`, every `paths` target is resolved relative to the `tsconfig.json` file, and each target must start with `./` or `../`.

If you are migrating an older config that still has `"baseUrl": "./src"`, delete `baseUrl` and prefix each target with the old base directory (`"app/*"` becomes `"./src/app/*"`). Then run a read-only check with the compiler you actually use:

```bash
npx tsc --noEmit
```

A leftover `baseUrl` stops TypeScript 7 with `TS5102`. A target without `./` stops it with `TS5090`.

Once you've set up your Path Mapping aliases, you can use them in your import statements like this:

```typescript
import { someModule } from "@customAlias/module";
import { anotherModule } from "@anotherAlias/module";
```

## When the code has to resolve at runtime: subpath imports

`paths` only tells the compiler where to look. Node.js ignores `tsconfig.json`, and its [TypeScript documentation](https://nodejs.org/api/typescript.html#paths-aliases) states that `paths` aliases are not transformed. If Node.js runs the emitted JavaScript or the `.ts` files directly, use package [subpath imports](https://nodejs.org/api/packages.html#subpath-imports), which must start with `#`:

```json
{
  "type": "module",
  "imports": {
    "#app/*": "./src/app/*"
  }
}
```

```typescript
import { someModule } from "#app/module.ts";
```

With `"module": "nodenext"` (plus `allowImportingTsExtensions` and `noEmit` when you import `.ts` files directly), TypeScript reads the same `imports` map, so the compiler and the runtime agree without a separate alias list. Check it with `npx tsc` first, then run the entry file on Node.js 24 (`node src/index.ts`) and confirm the import resolves.

And that's it! You've successfully set up Path Mapping in TypeScript and can now "Se3y" your imports.
