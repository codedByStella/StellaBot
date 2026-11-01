# StellaBot

**StellaBot is a Python desktop-companion prototype exploring persistent conversational identity, local memory, environmental context, and autonomous conversational initiative.**

This repository is a portfolio publication of the actual prototype source. It is intended to let readers inspect the implementation and understand how the systems fit together. It is not presented as a polished commercial application or a one-click installer.

> **Project status:** Prototype · Active development  
> **Development:** AI-assisted, human-directed  
> **Platform focus:** Windows desktop

## What the project explores

StellaBot approaches a conversational companion as a persistent application rather than a stateless chat window. A model response is only one part of the system. The application also manages conversation history, stored preferences and memories, environmental context, background initiative, voice-related components, and a desktop interface.

The central engineering question is how these separate systems can work together to produce continuity across sessions without treating every observation as permanent memory or every background event as a new user message.

The prototype brings together:

- **Conversation orchestration** for message handling, prompt construction, model requests, and response flow.
- **Persistent memory** backed by local SQLite and JSON data.
- **Context assembly** that combines relevant conversation and application context for a model request.
- **Attention and initiative systems** for tracking relevant state and supporting activity beyond direct message-response cycles.
- **Desktop activity awareness** using local screenshot capture and a rolling, timestamped activity reel.
- **Voice components** separated from the main conversation and interface code.
- **A local desktop interface** with application and background-worker lifecycle management.

## How a conversation is assembled

At a high level, an interaction passes through several distinct responsibilities:

1. The desktop interface receives the user's message.
2. Conversation handling coordinates the current exchange and available history.
3. Context management gathers relevant stored and temporary information.
4. Prompt construction combines the system behavior definition with the assembled context.
5. The model integration sends the request to the configured provider and receives a response.
6. The application processes the response and updates the relevant conversation and persistence layers.

The exact implementation is distributed across modules rather than concentrated in a single chatbot function. This separation makes the project useful to inspect as an example of application architecture: model communication, context selection, persistence, interface behavior, and background activity each have their own responsibilities.

## Memory and persistence

StellaBot distinguishes between conversational history, persistent companion information, preferences, and temporary application state.

SQLite provides structured local persistence. JSON files hold supporting state and configuration. The database package separates core database operations from history, preference, and companion-memory operations.

The repository also distinguishes checked-in reference material from mutable runtime data. Live application data is stored under `.companion_runtime/` rather than being written into the source tree during normal operation.

A reset utility archives the runtime directory before resetting local runtime state. Archiving is not the same as secure deletion.

## Environmental and visual context

The visual subsystem is designed around **local capture and activity metadata**, not a claim that the text model continuously receives or understands the desktop's raw pixels.

The application captures screenshots locally and manages a rolling reel of timestamped frames. It derives a timeline from information such as foreground-window titles, process names, timestamps, and periods of unchanged activity. That metadata can be included in conversational context to help the companion understand whether the user has been gaming, coding, or moving between applications.

The distinction matters:

- Screenshot capture and reel management happen locally.
- The conversational model receives a textual activity timeline, not the screenshot pixels.
- A storyboard can be generated as a local diagnostic artifact; it is not automatically attached to the model request.
- Window metadata can establish which application was active, but it cannot establish the text, objects, or events visible inside that application.

The reel implementation supports bounded short-term visual history, including frame handling and duplicate detection. This is temporary environmental context, not a substitute for persistent memory.

## Attention and initiative

The attention and initiative modules explore how a companion can maintain relevant state and participate without every action being triggered by a new user message.

These systems are separate from the main interface and have explicit lifecycle handling. Background work is coordinated with application shutdown so it does not continue producing output after the application has terminated.

This is prototype infrastructure for companion behavior, not a claim of unrestricted autonomous operation.

## Voice and desktop integration

Voice-related functionality is isolated in its own module and uses background processing rather than being embedded in the main conversation flow. The repository includes the associated integration points and asset structure; the presence of a component or placeholder does not imply that every voice path is currently configured or verified.

The desktop application is Windows-focused. Its interface, platform integration, background workers, and shutdown behavior are handled in separate parts of the package.

## Architecture

The original `companion.py` implementation grew to approximately 5,500 lines. The project was subsequently reorganized into a Python package with modules grouped by responsibility. The root entry point now delegates startup to `companion_app`.

| Component | Responsibility |
|---|---|
| `companion.py` | Application entry point |
| `companion_app/app.py` | Startup, application lifecycle, and shutdown coordination |
| `companion_app/state.py` | Shared application state |
| `companion_app/model.py` | Model-provider communication and conversation-history integration |
| `companion_app/conversation.py` | Message processing and conversational coordination |
| `companion_app/context.py` | Context selection and assembly |
| `companion_app/prompts.py` | System prompt and prompt construction |
| `companion_app/attention.py` | Attention state and companion tracking |
| `companion_app/initiative.py` | Background initiative management |
| `companion_app/voice.py` | Voice-related functionality |
| `companion_app/windows.py` | Windows-specific integration |
| `companion_app/vision.py` | Visual subsystem compatibility interface |
| `companion_app/visual/capture.py` | Local desktop capture |
| `companion_app/visual/reel.py` | Frame handling and rolling visual history |
| `companion_app/visual/storyboard.py` | Storyboard generation and persistence |
| `companion_app/database/common.py` | Database paths and shared persistence utilities |
| `companion_app/database/core.py` | Core database operations |
| `companion_app/database/history.py` | Conversation history persistence |
| `companion_app/database/preferences.py` | Preference persistence |
| `companion_app/database/companion_memory.py` | Companion memory operations |
| `companion_app/persistence.py` | Persistence compatibility interface |
| `companion_app/logging.py` | Application logging |
| `companion_app/patterns.py` | Supporting pattern and behavior utilities |
| `companion_app/interface/window.py` | Graphical interface |

### Engineering themes

- Domain-oriented module boundaries in place of a monolithic application file.
- Explicit startup and shutdown coordination.
- Local structured persistence with SQLite, supplemented by JSON state.
- Separation of durable memory from temporary environmental context.
- Background-worker lifecycle management.
- Compatibility interfaces around refactored functionality.
- A desktop-first application architecture without a separate hosted application backend.

## Runtime layout

| Path | Purpose |
|---|---|
| `companion.db` | Checked-in SQL schema/reference artifact; not the live runtime database |
| `companion_profile.json` | Companion profile/configuration seed |
| `.companion_runtime/` | Mutable runtime data |
| `.companion_runtime/companion_runtime.db` | Live application database |
| `.companion_runtime/companion_state.json` | Runtime state |
| `.companion_runtime/companion_chat_history.json` | Conversation history |
| `.companion_runtime/companion_debug.log` | Runtime diagnostics |

Generated runtime data is kept out of normal source control so local sessions do not continually modify the published source or accidentally add live personal data.

## Technology

- Python
- SQLite
- JSON
- Tkinter
- Windows desktop integration
- Model API integration
- Background threading
- Local filesystem persistence
- Desktop capture and image processing

## Development methodology

StellaBot was developed through an iterative, AI-assisted process. AI assistance is disclosed as part of the methodology, not presented as unaided authorship.

Models were used to accelerate implementation, explore alternatives, investigate unfamiliar problems, and assist with architectural changes. Generated output was treated as a proposal to evaluate, not as authoritative code.

The development process emphasizes:

1. **Challenge the reasoning.** Examine assumptions and require a defensible rationale for design decisions rather than accepting a plausible-sounding answer.
2. **Account for failure modes.** Context limits, conversational drift, hallucinations, and stateless API calls can affect reliability.
3. **Verify the implementation.** Review generated changes against the actual codebase, surrounding interfaces, imports, persistence behavior, and lifecycle requirements.
4. **Retain human responsibility.** Architecture, integration, review, testing, and final implementation decisions remain the developer's responsibility.

## Prototype status and verification

StellaBot has been launched locally on Windows. The repository includes implementation code and tests for selected subsystems, including initiative management and visual-reel behavior.

That evidence should not be confused with complete end-to-end validation. Runtime behavior can depend on local configuration, available model-provider credentials, installed dependencies, Windows integration, and external services. Not every API-dependent feature or long-running behavior has been verified across environments.

This is a working prototype and an evolving codebase. Interfaces and implementation details may change as the project develops.

## Publication and data handling

This repository publishes substantial, genuine source from the StellaBot prototype for portfolio inspection. It is not a mock implementation or a rewritten demonstration designed to resemble a private application.

The published code makes the architecture and implementation inspectable. Runtime databases, live conversation histories, credentials, and private personal data are not intended to be included as working user data.

The application is desktop-first and stores its runtime state locally. When model-provider functionality is used, conversation content and the context assembled for that request are sent to the configured provider. Desktop screenshots are captured locally; the text-model context uses the derived activity metadata described above. Diagnostic logging can record request/context details depending on configuration, so log settings and local data should be treated accordingly.

## Copyright and usage

Copyright © 2026 codedByStella. All rights reserved.

This repository is published for portfolio inspection and technical demonstration. Public visibility does not grant permission to copy, modify, redistribute, sublicense, or commercially use the material without prior written authorization.
