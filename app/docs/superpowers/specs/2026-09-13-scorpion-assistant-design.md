# Scorpion Assistant v0.1 Design

## Goal
Build a Windows-first desktop AI assistant named Scorpion with a distinct personality, text chat, push-to-talk voice input, spoken output, webcam vision, small local memory, and a safe whitelist of computer actions.

## Architecture
Scorpion is a Python desktop app. A CustomTkinter UI calls isolated services for AI, audio, camera, memory, wake-word parsing, and local commands. OpenAI Responses handles reasoning/vision, OpenAI transcription handles microphone audio, and OpenAI speech handles TTS. Local commands are parsed and executed only from an explicit whitelist.

## Core behavior
- Name and activation phrase: `Scorpion`.
- Voice input is push-to-talk in v0.1. If a transcript begins with `Scorpion`, the wake phrase is stripped before execution.
- Text input may be sent without a wake phrase because the user is already interacting with the Scorpion window.
- Personality is direct, playful, loyal, concise by default, multilingual, and never claims abilities it does not have.
- Local memory persists recent user/assistant turns in JSON.
- Camera capture can be sent with a question for visual analysis.
- Local actions support a whitelist such as browser, calculator, Notepad, Explorer, and opening specific URLs.
- Arbitrary shell commands are explicitly unsupported in v0.1.

## Platform
Windows 10/11, Python 3.11+.

## Configuration
Secrets live in `.env`. `OPENAI_API_KEY` is required for AI, speech transcription, and TTS. Models and voice are configurable by environment variables.

## Testing
Unit tests cover wake phrase parsing, command parsing, safe command behavior, and memory persistence. API, microphone, webcam, and GUI integration remain manual smoke tests because they require hardware/credentials.
