# Audio & MIDI Research for Agentic Coding

This document outlines the current landscape of MIDI and audio-routing tools designed specifically for AI agents and LLMs, primarily leveraging the **Model Context Protocol (MCP)**. This protocol allows these capabilities to be plugged directly into AI coding assistants.

## 1. Audio Routing & System Management
These tools give an AI agent the ability to manage the OS-level audio stack.

*   **`mac-audio-router-mcp` (by nickbeentjes)**
    *   **What it is:** An MCP server specifically for macOS CoreAudio. It includes a native C daemon for sub-millisecond latency.
    *   **Agent Capabilities:** Manage multi-zone device switching, control volumes, and re-route application audio on the fly. 
    *   **Relevance:** Could be used by an agent to automatically route Rekordbox's output to a recording pipeline without manual user configuration.
*   **Carla MCP Server**
    *   **What it is:** A massive toolkit for the open-source Carla audio plugin host.
    *   **Agent Capabilities:** Handles complex audio/MIDI routing matrices, plugin loading (VST/AU), and real-time spectrum analysis.

## 2. Real-Time MIDI Control
These tools allow an agent to interface with hardware or software via the MIDI protocol.

*   **`mcp-server-midi` (by sandst1)**
    *   **What it is:** A server that creates a virtual MIDI port on your system (e.g., "MCP MIDI Out").
    *   **Agent Capabilities:** Allows the LLM to send real-time `Note On`, `Note Off`, and `Control Change (CC)` messages to any DAW or software.
    *   **Relevance:** Demonstrates how an agent can act as a "virtual controller" or intercept/simulate hardware commands.
*   **AbletonMCP**
    *   **What it is:** Uses a Python MCP server and a custom Remote Script to let AI models control Ableton Live.
    *   **Agent Capabilities:** Start/stop transport, load tracks, write MIDI clips, and manipulate devices via natural language.

## 3. Audio Processing Automation
For post-processing and file management.

*   **MCP Audio Tweaker & Video/Audio Editing MCP**
    *   **What they are:** MCP servers that act as wrappers around `FFmpeg`.
    *   **Agent Capabilities:** Perform batch audio processing, sample rate conversion, and format adjustments.
    *   **Relevance:** Useful for automating post-recording tasks (e.g., normalizing the final WAV and encoding to MP3/FLAC).

## Future Application: Our Tool as an MCP Server
By packaging our Rekordbox Auto-Recorder as an MCP Server in the future, it would allow a user to instruct their AI assistant with natural language (e.g., *"Start the Rekordbox auto-recorder, set the hang-time to 10 seconds, and when the set is done, normalize the audio and save it to my Desktop"*), enabling the agent to execute the entire recording and post-processing workflow autonomously.