# 🎬 Cross-Platform Screen Recorder

A powerful, feature-rich screen recording application built with Python, PyQt6, and FFmpeg. Capture your entire desktop or specific windows with audio mixing capabilities on both Windows and Linux.

## ✨ Features

- **🖥️ Full Desktop Capture** - Record your entire screen including all windows
- **🪟 Window/Tab Capture** - Capture specific windows or browser tabs separately  
- **🎤 Audio Mixing** - Mix microphone and system audio using FFmpeg's amix filter
- **🔄 Cross-Platform** - Automatic OS detection (Windows 10/11 and Ubuntu Linux)
- **🎨 Modern Dark Mode GUI** - Clean and intuitive PyQt6 interface
- **🧵 Async Recording** - Non-blocking GUI with QThread for smooth operation
- **🔄 Live Window List** - Dynamic window detection with refresh capability

## 📋 Requirements

### Python
- Python 3.8 or higher

### Python Packages
```bash
pip install PyQt6
```

### System Dependencies

#### Windows
- **FFmpeg** - Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

#### Linux (Ubuntu/Debian)
```bash
# Install all required packages
sudo apt install ffmpeg pulseaudio-utils wmctrl xdotool x11-utils
```

**Package details:**
- `ffmpeg` - For video/audio encoding
- `pulseaudio-utils` - For audio device management
- `wmctrl` - For window management
- `xdotool` - For window selection
- `x11-utils` - For X11 utilities (xwininfo)

## 🚀 Installation

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/Akashtharu1/Screen-recorder.git
   cd Screen-recorder
   ```

2. **Install Python dependencies**
   ```bash
   pip install PyQt6
   ```

3. **Install system dependencies**
   
   **Windows:** Download and install [FFmpeg](https://ffmpeg.org/download.html)
   
   **Linux:**
   ```bash
   sudo apt install ffmpeg pulseaudio-utils wmctrl xdotool x11-utils
   ```

4. **Run the application**
   ```bash
   python screen_recorder.py
   ```

### Alternative: View Interactive Documentation

Open `index.html` in your web browser to see:
- Detailed feature descriptions
- Step-by-step installation guide
- Complete source code with syntax highlighting
- Download and copy options

## 📖 Usage

1. **Launch the application**
   ```bash
   python screen_recorder.py
   ```

2. **Select capture mode**
   - **Full Desktop** - Captures the entire screen
   - **Window/Tab** - Select a specific window from the dropdown list

3. **Configure audio settings** (Optional)
   - Enable/disable microphone recording
   - Enable/disable system audio recording
   - Both can be mixed together

4. **Choose output location**
   - Click "Browse..." to select where to save your recording
   - Default: `~/Videos/` (Linux) or `~/Documents/` (Windows)

5. **Start recording**
   - Click "Start Recording" button
   - The status bar will show recording status
   - GUI remains responsive during recording

6. **Stop recording**
   - Click "Stop Recording" button
   - Video will be saved to your selected location
   - Default format: MP4 (H.264 video, AAC audio)

## 🔧 Troubleshooting

### FFmpeg not found
**Error:** "FFmpeg not found. Please install FFmpeg and add it to PATH."

**Solution:**
- **Windows:** Ensure FFmpeg is installed and added to your system PATH
- **Linux:** Run `sudo apt install ffmpeg`
- Verify installation: `ffmpeg -version`

### No audio devices detected
**Error:** Audio recording fails or no audio in output

**Solution:**
- **Linux:** Install PulseAudio utilities: `sudo apt install pulseaudio-utils`
- Check audio devices: `pactl list sources` (Linux) or check Sound Settings (Windows)
- Ensure your microphone/audio device is not muted

### Window capture not working (Linux)
**Error:** Cannot list or capture specific windows

**Solution:**
```bash
sudo apt install wmctrl xdotool x11-utils
```

### Permission denied errors (Linux)
**Solution:**
```bash
chmod +x screen_recorder.py
```

## 🖥️ Platform-Specific Notes

### Windows
- Requires Windows 10 or later
- FFmpeg must be in system PATH
- Uses GDI screen capture method
- System audio capture requires appropriate drivers

### Linux
- Tested on Ubuntu 20.04+ and Debian-based distributions
- Uses X11 for window management (Wayland support limited)
- Requires X11 session for window capture features
- PulseAudio required for audio recording

## 🏗️ Technical Details

- **GUI Framework:** PyQt6
- **Video Encoding:** FFmpeg (H.264/libx264)
- **Audio Encoding:** AAC
- **Audio Mixing:** FFmpeg amix filter
- **Window Detection:** wmctrl + xdotool (Linux), win32gui (Windows)
- **Threading:** QThread for non-blocking recording

## 📝 License

MIT License - See the source code for full license text

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## 👤 Author

Developed with ❤️ using Python and PyQt6

---

**Note:** This is a cross-platform application. Some features may vary depending on your operating system and available system utilities.
