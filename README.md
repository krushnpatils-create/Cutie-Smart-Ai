<div align="center">

# Cutie Smart AI

**An intelligent, lightweight AI desktop assistant built for Windows.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Build](https://img.shields.io/badge/Build-PyInstaller%20EXE-2EA44F?style=for-the-badge)](https://pyinstaller.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Preview](#preview) • [Features](#features) • [Installation](#installation) • [Build EXE](#building-the-windows-executable) • [Project Structure](#project-structure) • [Roadmap](#roadmap)

</div>

---

## Overview

**Cutie Smart AI** is a modular Python-based desktop assistant designed to deliver fast, responsive, and intuitive interactions right on your Windows machine. Built with a clean architecture (`main.py` + `jarvis.py`) and powered by `pygame-ce`, it runs smoothly both from source and as a standalone `.exe` application.

---

## Preview

<div align="center">
  <img src="assets/preview.png" alt="Cutie Smart AI Screen Preview" width="750" />
</div>

---

## Features

| Feature | Description |
| :--- | :--- |
| **Smart Assistant Engine** | Modular command and AI response handling powered by `jarvis.py` and `main.py`. |
| **Interactive Interface** | Smooth audio-visual feedback and UI rendering via `pygame-ce`. |
| **Standalone Windows App** | Easily package into a single-file `.exe` with zero Python setup required for end users. |
| **Lightweight & Extensible** | Clean codebase ready for custom commands, voice modules, and API integrations. |

---

## Project Structure

```text
Cutie-Smart-Ai/
├── assets/
│   └── preview.png     # AI screen screenshot for documentation
├── main.py             # Application entry point & UI loop
├── jarvis.py           # Core assistant logic & command processing
├── requirements.txt    # Project dependencies
├── .gitignore          # Ignored build artifacts & environment files
└── README.md           # Project documentation
