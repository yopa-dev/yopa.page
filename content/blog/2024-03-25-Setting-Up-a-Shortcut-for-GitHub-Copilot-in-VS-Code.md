---
title: Setting Up a Shortcut for GitHub Copilot in VS Code
title-with-dash: Setting-Up-a-Shortcut-for-GitHub-Copilot-in-VS-Code
date: 2024-03-25
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "Learn how to configure a keyboard shortcut in VS Code to quickly access the GitHub Copilot chat panel."
categories:
  - Programming
  - VS Code
tags:
  - Git
  - GitHub
  - CLI
---

GitHub Copilot has become an indispensable tool for many developers, offering AI-powered code suggestions that streamline the coding process. However, constantly navigating through menus to access Copilot can disrupt your workflow. This tutorial will guide you through setting up a keyboard shortcut in Visual Studio Code (VS Code) to quickly open the GitHub Copilot chat panel.

> **Review note (2026-10-21):** VS Code now ships a default shortcut for the Chat view: `⌃⌘I` on macOS and `Ctrl+Alt+I` on Windows and Linux ([VS Code Copilot features](https://code.visualstudio.com/docs/copilot/reference/copilot-vscode-features)). Try that first. The custom binding below is now optional, and its command ID dates from 2024, so confirm it in the Keyboard Shortcuts editor before you rely on it.

### Use the built-in shortcut first

Press `⌃⌘I` (macOS) or `Ctrl+Alt+I` (Windows, Linux) to open the Chat view. If nothing happens, open **Keyboard Shortcuts**, search for "chat", and check whether another extension or a custom binding overrides that key.

### Optional: a custom toggle shortcut

Command IDs and default bindings can change with VS Code and the Copilot extension. Open Keyboard Shortcuts, search for the current Copilot Chat command by name, assign a non-conflicting key, and use the conflict view to verify context.

1. **Open the Command Palette in VS Code**
   Start by opening the Command Palette, which is the hub for accessing various commands in VS Code. You can open it by pressing `Cmd + Shift + P` on your keyboard.

2. **Access Keyboard Shortcuts File**
   In the Command Palette, type `keyboard shortcuts json`. This will bring up a list of options related to keyboard shortcuts. Select `Preference: Open Keyboard Shortcuts (JSON)` from the list. This action opens the `keybindings.json` file where you can define custom keyboard shortcuts.

3. **Edit the JSON File**
   In the `keybindings.json` file, you will define the shortcut for the GitHub Copilot chat panel. Insert the following code snippet:

   ```json
   {
       "key": "ctrl+alt+cmd+c",
       "command": "workbench.panel.chat.view.copilot.focus",
       "when": "editorFocus"
   },
   {
       // Move focus back to the Editor
       "key": "ctrl+alt+cmd+c",
       "command": "workbench.action.focusActiveEditorGroup",
       "when": "!editorFocus"
   }
   ```

   This configuration sets up `Ctrl + Alt + Command + C` as the shortcut to toggle the GitHub Copilot chat panel. The first part focuses on the Copilot chat panel when the editor is focused, and the second part returns focus to the editor if the Copilot panel is focused.

4. **Save and Test Your Shortcut**
   After adding the code, save your `keybindings.json` file. Test the new shortcut by pressing `Ctrl + Alt + Command + C` in the editor. If everything is set up correctly, you should be able to toggle the GitHub Copilot chat panel with this shortcut.

### Wrapping it up

After saving the binding, invoke it in the intended editor context and confirm that it opens the current Copilot Chat command without shadowing another shortcut.
