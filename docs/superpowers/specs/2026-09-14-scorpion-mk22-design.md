# Scorpion MK22 Design

## Status
Approved in chat through three design sections on 2026-09-14. This document captures the agreed architecture before implementation.

## Goal
Scorpion MK22 upgrades the existing Windows-first assistant into a more capable local-first desktop assistant with richer perception, structured long-term memory, safer computer control, improved voice interaction, intelligent local model routing, optional Google Drive memory sync, and a hardened signed update path.

The visible product name is **Scorpion MK22**. The technical release version is **v22.0.0**.

## Core Principles
- Local-first operation remains the default.
- Paid cloud AI calls remain behind explicit per-use approval.
- Risky computer actions require confirmation before execution.
- Screen understanding may run continuously and locally.
- Screen captures and raw visual data are not uploaded to cloud services automatically.
- Memory is local by default. Cloud sync is item- or project-level and requires explicit approval.
- Updates are signed, hash-verified, user-approved, self-checked, and rollback-capable.
- Adaptive learning may tune structured configuration and statistics, but may not rewrite arbitrary source code.

## 1. Perception and Computer Control

### 1.1 Context Monitor
Scorpion runs a local background context monitor that can continuously observe:
- active application and window title
- visible window list
- foreground process identity
- basic desktop state
- local screenshots or screen regions when deeper visual interpretation is needed

The monitor must avoid persisting continuous raw screen recordings. Short-lived screenshots used for local analysis are discarded unless the user explicitly asks to save them.

### 1.2 Vision
A dedicated local vision path interprets screenshots independently from the text model. The vision path should support:
- identifying visible UI elements
- describing the current screen
- grounding click/scroll/focus targets
- extracting task-relevant visual context

Cloud vision is not used automatically. Sending screenshots to any cloud provider requires an explicit confirmation scoped to that request.

### 1.3 Application Trust Model
Scorpion may control known trusted applications immediately. For a previously unseen application, it must request one-time permission before interacting with it. The decision is stored locally in a structured trust registry.

Trust is application-scoped, not a blanket permission for dangerous actions inside that application.

### 1.4 Action Risk Classes
Actions are classified before execution:

**Low-risk actions** may run without confirmation, for example:
- focus or switch windows
- scroll
- navigate within a trusted application
- open an already approved application
- read visible local state

**Mutating actions** require confirmation, for example:
- move or rename files
- change settings
- edit persistent application data

**Critical actions** always require confirmation, for example:
- delete files or data
- install or uninstall software
- send messages, emails, or posts
- make purchases or payments
- change security settings
- execute commands with elevated privileges

The confirmation UI must describe the concrete action, target, and likely consequence.

## 2. Voice

### 2.1 Language and Voice
The default synthetic voice changes from Swiss German to a calm, natural female **de-DE High German** voice.

The default voice should be configurable, but MK22 must ship with a de-DE voice as the out-of-box default. Speaking rate remains slightly reduced to preserve the existing composed Scorpion identity.

### 2.2 Barge-in
Scorpion must support user interruption while TTS is active. When the user begins speaking, TTS should stop or duck and the listener should capture the new command without causing self-trigger loops.

### 2.3 Existing Voice State Machine
The existing state machine remains the foundation:
`STANDBY -> ACKNOWLEDGED -> WAITING_COMMAND/LISTENING -> THINKING -> SPEAKING`

Wake behavior and the 20-second post-wake command window remain intact unless later testing shows a specific regression.

## 3. Structured Long-Term Memory

### 3.1 Memory Model
MK22 introduces a structured long-term memory store separate from the short rolling conversation history.

Memory entries contain at minimum:
- stable ID
- category
- title or concise subject
- content
- importance score or level
- created timestamp
- updated timestamp
- source/origin
- optional project association
- cloud sync state

Initial categories:
- projects
- decisions
- preferences
- open tasks
- important facts

### 3.2 Local-First Storage
Local storage is authoritative. Normal conversations, temporary thoughts, and sensitive runtime context are not automatically promoted to long-term memory.

Scorpion may propose saving information when it appears important, but the implementation should distinguish between harmless local capture and cloud synchronization. Secrets such as passwords, API tokens, private keys, or authentication cookies must never be stored as normal memory entries.

### 3.3 Google Drive Hybrid Sync
Google Drive is the first supported cloud memory backend.

Sync policy:
- local copy always exists first
- Scorpion may identify an entry or project block as a good candidate for backup
- Scorpion asks the user for permission before the first upload of that specific memory item or project block
- only approved structured memory data is uploaded
- raw screenshots, audio, tokens, passwords, and whole unfiltered chat logs are excluded
- sync state and remote revision metadata are tracked locally

A sync failure must never delete or corrupt the local authoritative copy.

## 4. Model Routing

### 4.1 Routing Goals
Scorpion chooses the cheapest and fastest capable local path for each task.

Routing tiers:
- deterministic/local command handlers for simple system commands
- lightweight local text model for ordinary conversation and short reasoning
- stronger local model for harder reasoning when hardware permits
- dedicated local vision model for screen understanding
- paid cloud AI only after explicit approval

### 4.2 Hardware-Aware Selection
The existing hardware profile mechanism remains. MK22 may record local performance statistics such as latency and success/failure counts and use those to improve model selection.

It must not silently download multi-gigabyte models. New large model downloads require user approval.

### 4.3 Adaptive Configuration
Adaptive learning may modify structured settings such as:
- chosen local model
- model routing thresholds
- microphone/VAD profile
- voice preferences
- app trust decisions
- per-model latency statistics

Adaptive code may not arbitrarily modify executable source files.

## 5. Security and Privacy Boundaries

### 5.1 Sensitive Data
The following must remain excluded from source control, cloud memory sync, and ordinary diagnostics:
- `.env`
- API keys and tokens
- private release signing keys
- authentication cookies
- passwords
- raw continuous screen recordings
- raw continuous microphone recordings

### 5.2 Confirmation Scope
Confirmation should be specific rather than generic. A previous permission to use an application does not authorize deletion, purchases, messages, installations, or other high-impact actions.

### 5.3 Auditability
Locally, Scorpion should maintain a lightweight action log containing action type, target, timestamp, confirmation requirement, and outcome. The log should avoid storing secret contents.

## 6. Update and Release Architecture

### 6.1 Release Identity
- Product name: **Scorpion MK22**
- Technical version: **v22.0.0**

### 6.2 Release Pipeline
The release path is:

`Code -> Windows CI -> tests -> release build -> signed manifest -> GitHub Release -> Scorpion update check -> user confirmation -> download -> signature/hash verification -> install -> self-check -> success or rollback`

### 6.3 Required Release Assets
At minimum the updater expects:
- `manifest.json`
- `manifest.sig`
- `SCORPION_update.zip`

A full human-download package may also be published as:
- `SCORPION_MK22.zip`

Release notes must be published with the GitHub Release.

### 6.4 Signing
The existing Ed25519 trust model remains. The public key is embedded in the application/repository. The private signing key must remain outside the public repository.

Every release manifest is signed with the private key, and package/file SHA-256 hashes are verified before installation.

### 6.5 Release Guard
A release may only be published after the Windows CI suite passes. The release workflow must fail closed if:
- tests fail
- required release files are missing
- manifest signature is invalid
- package hash validation fails

### 6.6 Installation Behavior
Scorpion may automatically check metadata for updates. It must not install a new version until the user explicitly confirms installation.

Before applying files:
- preserve user settings and local memory
- preserve `.env`
- preserve installed local models
- create a rollback backup

After applying files:
- run self-check
- if self-check passes, mark update successful
- if self-check fails, restore the previous working version

## 7. Testing Strategy

MK22 implementation must extend the existing test suite with tests for:
- de-DE voice default
- barge-in state transitions
- structured memory CRUD and persistence
- memory categorization and project association
- Google Drive sync approval state and failure handling
- application trust registry
- action risk classification
- confirmation gating for mutating and critical actions
- screen context monitor state handling
- model routing decisions
- update version comparison for v22.0.0
- signed release verification and rollback behavior

The existing Windows GitHub Actions CI remains the release gate. Tests must not require real Google Drive credentials, paid OpenAI calls, or destructive desktop actions.

## 8. Error Handling

- Vision failure falls back to text/window metadata rather than crashing the assistant.
- Google Drive failure leaves local memory intact and reports sync as pending/failed.
- App automation failure returns control to the user and must not retry dangerous actions blindly.
- Model failure should allow fallback to another approved local model where available.
- Update failure triggers rollback and records the failure reason locally.

## 9. Implementation Boundaries

MK22 does not include unrestricted autonomous self-modification.

MK22 does not grant blanket permission for destructive actions.

MK22 does not automatically upload screen, microphone, or complete conversation data to Google Drive or any AI provider.

MK22 does not silently install large models or paid services.

## 10. Success Criteria

MK22 is ready for release when:
- the default TTS voice is de-DE High German
- user barge-in works without wake-loop regressions
- structured local memory persists and can associate entries with projects
- approved memory entries can sync to Google Drive without making cloud storage authoritative
- new applications require first-use trust approval
- dangerous computer actions are always confirmation-gated
- local screen context can be continuously observed without automatic cloud upload
- model routing remains local-first and hardware-aware
- all Windows CI tests pass
- the signed v22.0.0 update package validates and self-checks successfully
- a failed update can roll back to the previous working version
