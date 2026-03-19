# satfinderbylatlong
A program for determining the beam for pointing at a satellite, adapted for work with Intelsat (Velocity)

# 🛰️ Satellite Beam Finder

A standalone Python tool to find which satellite beams cover a given geographic point (longitude/latitude) and display carrier information (frequency, polarization, symbol rate).

![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![No Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

## 📋 Description

Satellite Beam Finder loads satellite configuration data from a JSON file and determines which satellite beams cover a specific location on Earth. It uses a pure Python implementation of the point-in-polygon algorithm (ray casting) with **no external dependencies**.

For each matching beam, the tool displays:
- Satellite ID and orbital position
- Beam ID
- Available carriers (transponders) with:
  - Center frequency (MHz/GHz)
  - Polarization (RX:V / RX:H)
  - Symbol rate (symbols/s)
  - Carrier type (DVBS2, etc.)

## ✨ Features

- ✅ **No external libraries required** - works with pure Python
- ✅ Interactive command-line interface
- ✅ Real-time beam search by coordinates
- ✅ Detailed carrier information display
- ✅ Support for special commands (`stats`, `list`, `help`)
- ✅ Input validation for coordinates
- ✅ Duplicate beam removal
- ✅ Handles invalid polygons gracefully

## 🚀 Getting Started

### Prerequisites

- Python 3.6 or higher installed on your system
- Your satellite configuration JSON file (`CONSTELLATION_OPT.json`)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/artur-devops/satfinderbylatlong.git
   cd satfinderbylatlong
