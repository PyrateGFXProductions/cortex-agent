# NeuralCode

A minimal coding agent harness in Python, built to show how the pieces of a coding agent fit together.

This is the repo for the Neural Breakdown video on building Codign Agent from scratch. [You can watch the full walkthrough here.](https://youtu.be/Lu1UWqVTbQg)

## Features

- Interactive terminal chat 
- Tools for running shell commands, reading and writing files, and making targeted edits.
- Configurable model and OpenAI-compatible API endpoint.
- Tool permissions and shell sandboxing on macOS and Linux
- Skills loaded from project and user `.agents/skills` directories.
- Subagents for exploring a codebase in a separate context window.
- Todo tracking for tasks with multiple steps.
- Saved chat sessions, with `/sessions` to reopen them and `/rewind` to go back in the conversation.
- Automatic context compaction, plus `/compact` to trigger it manually.
- Git branch context and reminders when files change between turns.

## Support

If you find this helpful, consider supporting on Patreon — it hosts all code, projects, slides, and write-ups from the YouTube channel.

[<img src="https://c5.patreon.com/external/logo/become_a_patron_button.png" alt="Become a Patron!" width="200">](https://www.patreon.com/NeuralBreakdownwithAVB)
