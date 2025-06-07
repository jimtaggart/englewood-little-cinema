# Englewood Little Cinema

A Raspberry Pi-based video player for the Englewood Little Cinema installation. This project allows for simple, one-button operation of a video display system, perfect for small cinema installations or art exhibits.

## Features

- Single button operation for video playback
- Sequential video playing from a directory
- Automatic house lights control
- Screen power management
- Support for various video formats (mp4, m4v, mov, avi, mkv)
- Configurable audio output (HDMI, local, or both)
- Optional splash screen
- Safe shutdown support via GPIO

## Requirements

- Raspberry Pi (tested on Raspberry Pi 4)
- omxplayer (hardware-accelerated video player)
- Python 3.x
- Required Python packages:
  - RPi.GPIO
  - pigpio

## Installation

1. Install the required system packages:
```bash
sudo apt-get update
sudo apt-get install omxplayer python3-pip python3-rpi.gpio
```

2. Install the required Python packages:
```bash
pip3 install pigpio
```

3. Clone this repository:
```bash
git clone [repository-url]
cd englewood-little-cinema
```

## Usage

Basic usage:
```bash
python3 minitheatre.py --video-dir /path/to/videos
```

Full options:
```bash
python3 minitheatre.py --help
```

### Command Line Options

- `--audio`: Audio output (hdmi, local, or both)
- `--video-dir`: Directory containing video files
- `--no-autostart`: Don't start playing a video on startup
- `--no-loop`: Don't loop the active video
- `--restart-on-press`: Restart current video if its button is pressed
- `--gpio-pins`: GPIO pin configuration
- `--debug`: Enable debug mode
- `--splash`: Splash screen image
- `--no-osd`: Disable on-screen display
- `--shutdown-pin`: GPIO pin for shutdown

## Hardware Setup

1. Connect a button to GPIO pin 26 (default)
2. Connect house lights control to GPIO pin 18 (PWM)
3. Connect HDMI display
4. (Optional) Connect audio output

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.

## Acknowledgments

This project is based on the rpi-vidlooper project and East Van Vodville mini theater. It was adapted for the Englewood Little Cinema installation.
