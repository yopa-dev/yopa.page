---
title: Passing Command-Line Arguments to a TypeScript Script using NPM
date: 2023-08-18T01:25:00-04:00
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "A step-by-step guide on passing command-line arguments to a TypeScript script using npm run."
categories:
    - TypeScript Development
tags:
  - TypeScript
  - Node.js
  - npm
  - CLI
  - Input Validation
---

> **Review note (2026-10-21):** The original `"start": "ts-node your-script-file.ts"` no longer works with the current `typescript` package. With TypeScript 7.0.2 installed, ts-node 10.9.2 crashes at startup with `TypeError: Cannot read properties of undefined (reading 'fileExists')`. The script now uses Node.js's built-in type stripping (stable since Node.js 24.12), and `tsx` is the fallback. The argument handling is unchanged.

## Argument boundary and validation

`npm run script -- arg1 arg2` remains the portable argument boundary. Use the project-pinned TypeScript runner or compiled JavaScript, validate `process.argv` with a maintained parser for nontrivial CLIs, and return a nonzero exit code for invalid input.

## Introduction

In modern JavaScript and TypeScript development, `npm` scripts are commonly used to streamline and simplify various tasks. However, there may be occasions when you need to pass arguments to these scripts to make them more dynamic. In this article, we'll explore how to pass command-line arguments to a TypeScript script using `npm run`.

## Setting up NPM to Run Your TypeScript Script

To run your TypeScript script using the `npm run` command, you can define a script in your `package.json` file. Here's a step-by-step guide to help you set it up:

1. Check the runtime first: `node --version`. Node.js runs `.ts` files that use only erasable TypeScript syntax: type stripping is on by default since v22.18.0 and v23.6.0, and stable since v24.12.0. Use a supported LTS line (22 or 24).
2. Install TypeScript only if you want type checking (`npm install --save-dev typescript` and `npx tsc --noEmit`). Node.js strips types but never checks them.
3. Add a script entry to the `scripts` section of your `package.json` that runs the file with `node`.

## Passing Parameters with NPM Run

1. **Handling Arguments in TypeScript**:

    In your TypeScript script, Node.js provides a global object called `process.argv` which is an array containing the command-line arguments passed when the process was launched. The first two values are the node executable and your script's path, so you'll usually want to access the arguments starting from index 2:

    ```typescript
    const args = process.argv.slice(2);
    ```

    For our use case, we want to retrieve the `arg` argument:

    ```typescript
    const profileArg = args.find((arg) => arg.startsWith("--arg="));
    const profileName = profileArg ? profileArg.split("=")[1] : "default";
    ```

2. **Updating the NPM Script**:

    Your `package.json` scripts entry can look like this:

    ```json
    "scripts": {
      "start": "node your-script-file.ts"
    }
    ```

    Type stripping only removes annotations, so TypeScript features that need code generation, such as `enum` and parameter properties, fail with `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX`. If your script uses them, or you are on an older Node.js line, use `tsx` instead, as the [Node.js TypeScript documentation](https://nodejs.org/api/typescript.html#full-typescript-support) suggests:

    ```bash
    npm install --save-dev tsx
    ```

    ```json
    "scripts": {
      "start": "tsx your-script-file.ts"
    }
    ```

    Avoid `ts-node` for new setups. It loads the TypeScript compiler API, which TypeScript 7.0 does not ship.

3. **Executing the Script with Arguments**:

    When running your script, use the following format to pass in the `arg` argument:

    ```
    npm run start -- --arg=myProfile
    ```

    The `--` after `npm run start` indicates that the subsequent arguments should be passed directly to the invoked script. npm echoes the final command (`node your-script-file.ts --arg=myProfile`), so you can confirm the argument reached the script. Run it once without the argument as well and check that the `"default"` fallback is used.

## Advanced: Using Argument Parsers

For more advanced command-line argument parsing, consider using libraries like `yargs` or `commander`. They offer a plethora of features such as default values, required arguments, aliases, and much more, which can make your scripts more robust and user-friendly.

## Conclusion

Passing command-line arguments to your TypeScript scripts via `npm run` can greatly enhance their flexibility. Whether you're looking to provide different configurations, paths, or any other kind of data, this method can simplify and streamline your development process.
