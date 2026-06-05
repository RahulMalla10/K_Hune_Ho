# KHUNEHO: Neural News Analysis System

KHUNEHO is a local-first news intelligence system that produces structured predictions with confidence scores and timelines. This system uses model : Qwen2.5-7B-Instruct (GGUF format) through llama-cpp-python. The model is downloaded from: https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF 

This represents the base project setup. 


## Table of Contents

- [System Requirements](#system-requirements)
- [Configuration](#configuration)
- [Setup and Run](#project-setup)

## System Requirements

- Operating System: Linux, Windows (WSL2 recommended), or macOS with Metal support.
- Python: 3.10 or higher.
- RAM: 16GB system RAM.
- Disk space: 10GB free for models and dependencies.


## Configuration

Set up your environment variables based on the template. You can change the model by editing .env after you copy the files.


## Setup and Run

Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python setup.py # this run the setup file and download the model required for project
python run.py # for Cli
uvicorn app:app # web-based interface
```

Linux and macOS:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python setup.py # this run the setup file and download the model required for project
python run.py # for Cli
uvicorn app:app # web-based interface
```

If the project requires configuration, create or update the environment variables as needed before running.