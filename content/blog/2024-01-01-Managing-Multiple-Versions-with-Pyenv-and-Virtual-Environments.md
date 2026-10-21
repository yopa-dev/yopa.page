---
title: Managing Multiple Versions with Pyenv and Virtual Environments
date: 2024-01-01
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "Dive into the essentials of Python development by learning how to manage multiple Python versions with Pyenv and create isolated project environments using virtual environments."
categories:
  - Python
tags:
  - Python
  - Package Management
  - CLI
---

![oni working on python](images/oni-python-1.webp)

> **Review note (2026-10-21):** The install example pinned `3.13.5`, and 3.13 now receives security fixes only. The example now installs the 3.14 bugfix line through pyenv prefix resolution, with a read-only `pyenv latest --known` check first ([Python downloads](https://www.python.org/downloads/), [pyenv commands](https://github.com/pyenv/pyenv/blob/master/COMMANDS.md#pyenv-install)). Step 4 was also relabeled: `pyenv local` pins the version for the current project, not globally.

## Managing Multiple Versions with Pyenv and Virtual Environments

When working on multiple projects with different Python versions, it's crucial to avoid conflicts and ensure that each project uses the correct version and dependencies. This is where virtual environments come in. They are isolated Python environments that let you manage packages and dependencies specific to a project without affecting the global Python installation.

## Installing Python Using Homebrew on macOS

Before setting up virtual environments, ensure you have the desired versions of Python installed:

1. **Install Homebrew**: Install Homebrew, a package manager for macOS, with the following command:
   e.g.

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python**: Use Homebrew to install the latest version of Python:

   ```bash
   brew install python
   ```

## Managing Multiple Python Versions with pyenv

Select a release that is still supported on the [Python versions page](https://devguide.python.org/versions/). The concrete version below is an example; pin the version required by the project and use the same value in CI.

`pyenv` is an indispensable tool for managing multiple Python versions:

1. **Install pyenv**: Install `pyenv` using Homebrew:

   ```bash
   brew install pyenv
   ```

2. **Configure Your Shell**: Add the following to your shell configuration file (`.bashrc`, `.zshrc`, etc.) and restart your terminal or source the profile:

   ```bash
   eval "$(pyenv init --path)"
   eval "$(pyenv init -)"
   ```

3. **Install Python Versions**: Check which patch pyenv would install (read-only), then install the newest patch of a supported line:

   ```bash
   pyenv latest --known 3.14
   pyenv install 3.14
   ```

   A prefix such as `3.14` resolves to the latest patch pyenv knows about. If that is older than the patch listed on [python.org](https://www.python.org/downloads/), update pyenv first.

4. **Pin the Project's Python Version**: In the project directory, write the exact installed version to `.python-version`:

   ```bash
   pyenv local "$(pyenv latest 3.14)"
   python --version
   ```

   `pyenv local` affects only this directory and its subdirectories. Use `pyenv global` for a user-wide default. `python --version` confirms which interpreter is active.

## Creating and Activating Virtual Environments

Virtual environments are created and activated to isolate project dependencies:

1. **Creating a Virtual Environment**: Navigate to your project directory and create a virtual environment:

   ```bash
   python3 -m venv .venv
   ```

   Replace `.venv` with your preferred environment name.

2. **Activating the Virtual Environment**: Activate the virtual environment to use it:

   ```bash
   source .venv/bin/activate
   ```

   Upon activation, your shell prompt might change to indicate the active environment. Now, the environment's Python version and packages are isolated from the rest of your system.

## How Virtual Environments Set the Correct Python Version and Environment Variables

When a virtual environment is activated:

- **Python Version**: The virtual environment uses the Python version it was created with. Even if you have multiple versions installed on your system, the environment will only have access to and use the specific version it was created with.

- **Environment Variables**: The activation script adjusts environment variables like `PATH` to ensure that when you invoke `python` or `pip`, you're using the versions installed in the virtual environment's bin directory. This means any Python scripts you run or packages you install will be confined to the virtual environment.

- **Isolation**: This isolation prevents different projects from interfering with each other's dependencies. Each virtual environment operates independently, with its own Python binaries and site packages.

## Deactivating Virtual Environments

To stop using a virtual environment and revert to your global Python setup, simply run:

```bash
deactivate
```

Your shell's prompt will return to normal, and you'll be using the global Python version and packages again.
