---
title: FlexPave
emoji: 🏢
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# FlexPave Engineering Suite

A robust pavement design and optimization suite that interfaces with the legacy IIT Pave software to perform advanced structural analysis and multi-objective optimization (NSGA-II / Smart Search).

## Architecture

- **Backend (Hugging Face Spaces):** A FastAPI service utilizing a secure Bridge pattern to execute the legacy Fortran-based `IITPFILE.exe` via Wine within a Docker container.
- **Frontend (GitHub Pages):** A React/Vite web application providing an intuitive interface for entering pavement layers, load configurations, and evaluation parameters.

## Deployment
This repository is configured to be deployed as a Docker Space on Hugging Face.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

