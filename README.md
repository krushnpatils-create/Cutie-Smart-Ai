<div align="center">

# Cutie Smart AI

**An intelligent, lightweight AI desktop assistant built for Windows.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![GUI](https://img.shields.io/badge/UI-CustomTkinter%20%26%20Pygame-1F6FEB?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Build](https://img.shields.io/badge/Build-PyInstaller%20EXE-2EA44F?style=for-the-badge)](https://pyinstaller.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Preview](#preview) • [Features](#features) • [Installation](#installation) • [CMD Build & Deploy](#cmd-build--deployment) • [Project Structure](#project-structure) • [Roadmap](#roadmap)

</div>

---

## Overview

**Cutie Smart AI** is a modular Python-based desktop assistant designed to deliver fast, responsive, and intuitive interactions right on your Windows machine. Built with a clean architecture (`main.py` + `jarvis.py`) and powered by `CustomTkinter`, `SpeechRecognition`, and `pygame-ce`, it runs smoothly both from source and as a standalone `.exe` application.

---

## Preview

<div align="center">
  <img width="1919" height="1079" alt="Cutie Smart AI Screen Preview" src="https://github.com/user-attachments/assets/2544f609-6df8-40b6-99c3-3fec11ad0ca1" />
</div>

---

## Features

| Feature | Description |
| :--- | :--- |
| **Smart Assistant Engine** | Modular command and AI response handling powered by `jarvis.py` and `main.py`. |
| **Modern Desktop UI** | Sleek desktop interface built with `CustomTkinter` and audio-visual rendering via `pygame-ce`. |
| **Voice & Speech Support** | Integrated speech recognition capabilities for hands-free assistant interaction. |
| **Standalone Windows App** | Package into a single-file `.exe` using PyInstaller with zero Python setup required for end users. |

---

## Project Structure

```text
Cutie-Smart-Ai/
├── main.py             # Application entry point & UI loop
├── jarvis.py           # Core assistant logic & command processing
├── requirements.txt    # Project dependencies
├── .gitignore          # Ignored virtual environments, build artifacts & secrets
└── README.md           # Project documentation
