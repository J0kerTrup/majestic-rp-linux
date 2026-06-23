# Contributing to majestic-rp-linux 🐧🎮

Thank you for your interest in contributing to **majestic-rp-linux**.

This project focuses on improving the experience of running **Majestic RP / GTA V on Linux**, mainly through **Steam**, **Proton**, and **Wine**.

Community help is welcome, especially with testing, bug reports, compatibility notes, documentation, packaging, and Linux-specific fixes.

---

## Compatibility note

Steam is the main supported version and is expected to work out of the box.

Rockstar Launcher and Epic Games versions may require manual configuration and are not guaranteed to work on every setup.

Steam Deck support is experimental. Some setups may require additional fixes, custom Proton versions, launch options, Redux/mod-related adjustments, or other manual configuration.

---

## How you can contribute

You can help the project by:

* Reporting bugs
* Testing on different Linux distributions
* Testing different Proton / Wine versions
* Improving documentation
* Sharing working configurations
* Improving installation scripts
* Improving packaging for Linux distributions
* Fixing launcher, patcher, or compatibility issues
* Helping other users in Discussions

---

## Before opening an Issue

Before creating a new Issue, please check:

1. Existing Issues
2. Existing Discussions
3. The README
4. Recent releases or changelogs

If your question is not a confirmed bug, please start with a Discussion first.

Use **Discussions** for:

* Questions
* Setup help
* Ideas
* General troubleshooting
* Compatibility notes
* Steam Deck experiments
* Rockstar / Epic manual setup notes

Use **Issues** for:

* Confirmed bugs
* Reproducible crashes
* Broken scripts
* Packaging problems
* Missing or incorrect functionality

---

## Bug report format

When reporting a bug, please include as much useful information as possible.

```txt
OS:
Device: Desktop / Laptop / Steam Deck / Other
Desktop Environment:
GPU:
Game version: Steam / Rockstar / Epic Games
Proton / Wine version:
Mods / Redux installed: Yes / No

What you tried:
What happened:
What you expected:

Logs:
Screenshots:
```

Please do not post only “it does not work”.
Without logs and system information, it is very hard to understand the problem.

---

## Logs

Logs are very important.

When possible, include launcher logs, patcher logs, Proton/Wine output, terminal output, screenshots, or crash messages.

Please remove private information before posting logs, for example:

* Account names
* Emails
* Tokens
* Personal paths if needed
* Server credentials
* API keys

Never publish passwords, tokens, cookies, or private keys.

---

## Pull Requests

Pull Requests are welcome.

Before opening a Pull Request:

1. Make sure your change is related to the project.
2. Keep the change focused.
3. Avoid mixing unrelated fixes in one PR.
4. Explain what was changed and why.
5. Mention which OS / Proton / Wine version you tested with.

Good Pull Requests usually include:

* Clear title
* Short explanation
* Screenshots if UI changed
* Logs if launch behavior changed
* Testing notes
* Related Issue or Discussion link if available

---

## Code style

Please keep the project simple and readable.

General rules:

* Do not hardcode user-specific paths.
* Do not hardcode secrets, tokens, or credentials.
* Prefer clear names over clever names.
* Keep scripts understandable.
* Add comments only where they are useful.
* Avoid large unrelated rewrites.
* Keep Linux paths and permissions in mind.
* Do not break Steam support while improving other platforms.

---

## Platform support

The main target is Linux.

Primary supported path:

```txt
Steam + GTA V + Proton
```

Other setups may work, but can require manual fixes:

```txt
Rockstar Launcher
Epic Games
Steam Deck
Custom Proton builds
Wine prefixes
Redux/modded setups
```

If you are contributing support for one of these setups, please document what was tested and what still does not work.

---

## Testing checklist

Before submitting a change, please test what you can:

```txt
Launcher starts:
Game path detection works:
Steam version works:
Proton/Wine launch works:
Patcher does not break existing files:
Logs are readable:
No private paths or secrets are committed:
```

If you cannot test everything, mention that clearly in the Pull Request.

---

## Documentation changes

Documentation improvements are welcome.

Useful documentation contributions include:

* Installation steps
* Troubleshooting guides
* Steam Deck notes
* Proton version notes
* Wine prefix notes
* Distro-specific dependencies
* Known issues
* Fixes for common errors

Please keep documentation clear and practical.

---

## Community behavior

Please be respectful and helpful.

We understand that Linux gaming, Proton, Wine, launchers, and GTA V compatibility can be frustrating, but aggressive or toxic behavior does not help the project.

Good reports and clear testing help everyone.

---

## Security

Do not open public Issues with sensitive information.

Sensitive information includes:

* Tokens
* Passwords
* Cookies
* Private keys
* API keys
* Personal account data

If you accidentally posted sensitive information, delete it immediately and rotate the affected credentials.

---

## Final note

This project is community-driven.

Every useful bug report, test result, fix, guide, or compatibility note helps make Majestic RP on Linux better for everyone.

Thanks for contributing 🐧🎮
