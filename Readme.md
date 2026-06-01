# KHUNEHO: Neural News Analysis System

KHUNEHO (Knowledge-based Hierarchical Universal Neural Engine for Holistic Outlook) is a local-first news intelligence system that produces structured predictions with confidence scores and timelines.

This represents the base project setup. 

**Note to Team Members:** Please update this README.md file (especially the Features, Usage, and Architecture sections) to reflect your specific contributions when you add your modules!

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Team Git Workflow](#team-git-workflow)

## System Requirements

- Operating System: Linux, Windows (WSL2 recommended), or macOS with Metal support.
- Python: 3.10 or higher.
- RAM: 16GB system RAM.
- Disk space: 10GB free for models and dependencies.

## Installation

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py

## Configuration

Set up your environment variables based on the template. You can change the model by editing .env after you copy the files.

## Agent Manager

`src/agent_manager.py` contains the `AgentManager` class that initializes the LLM and runs multiple domain-specific reasoning agents against news article data. It loads the local Llama model using configuration values from `src/config.py`, builds prompts for domains such as sentiment, financial, geopolitical, legal, and more, and returns structured JSON prediction output for each domain.

## Setup and Run

Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Linux and macOS:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

If the project requires configuration, create or update the environment variables as needed before running.