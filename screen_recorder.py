#!/usr/bin/env python3
"""
Cross-Platform Screen Recorder with Window/Tab Capture
A robust screen recording application for Windows and Linux
using PyQt6 and FFmpeg.

Features:
- Dynamic OS detection (Windows/Linux)
- Full desktop capture OR specific window/tab capture
- Microphone + System Audio mixing via FFmpeg amix filter
- Modern dark-mode PyQt6 GUI
- Async recording with QThread (non-freezing GUI)
- Live window list with refresh capability

Requirements:
- Python 3.8+
- PyQt6: pip install PyQt6
- FFmpeg: Must be installed and in PATH
- Linux: xdotool, xwininfo (sudo apt install xdotool x11-utils)

Author: AI Assistant
License: MIT
"""

import sys
import os
import subprocess
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QMessageBox,
    QFileDialog, QGroupBox, QGridLayout, QStatusBar, QRadioButton,
    QButtonGroup, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor


# =============================================================================
# OS DETECTION
# =============================================================================

class OSDetector:
    """Utility class for OS detection and platform-specific configurations."""
    
    @staticmethod
    def get_os() -> str:
        """Detect the current operating system."""
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system == 'linux':
            return 'linux'
        elif system == 'darwin':
            return 'macos'
        return 'unknown'
    
    @staticmethod
    def is_windows() -> bool:
        return OSDetector.get_os() == 'windows'
    
    @staticmethod
    def is_linux() -> bool:
        return OSDetector.get_os() == 'linux'


# =============================================================================
# FFMPEG DEPENDENCY CHECK
# =============================================================================

class FFmpegChecker:
    """Utility class to verify FFmpeg installation."""
    
    @staticmethod
    def check_ffmpeg_installed() -> Tuple[bool, str]:
        """
        Check if FFmpeg is installed and accessible.
        
        Returns:
            Tuple of (is_installed: bool, version_or_error: str)
        """
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if OSDetector.is_windows() else 0
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=creationflags
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                return True, version_line
            return False, "FFmpeg returned non-zero exit code"
        except FileNotFoundError:
            return False, "FFmpeg not found. Please install FFmpeg and add it to PATH."
        except subprocess.TimeoutExpired:
            return False, "FFmpeg check timed out"
        except Exception as e:
            return False, f"Error checking FFmpeg: {str(e)}"


# =============================================================================
# WINDOW ENUMERATOR - For capturing specific windows/tabs
# =============================================================================

class WindowEnumerator:
    """Class to enumerate open windows on the system for selective capture."""
    
    def __init__(self):
        self.os_type = OSDetector.get_os()
    
    def get_open_windows(self) -> List[Dict[str, str]]:
        """
        Get list of open windows that can be captured.
        
        Returns:
            List of dicts with 'name', 'id', 'geometry' keys
        """
        if self.os_type == 'windows':
            return self._get_windows_windows()
        elif self.os_type == 'linux':
            return self._get_linux_windows()
        return []
    
    def _get_windows_windows(self) -> List[Dict[str, str]]:
        """Get open windows on Windows using PowerShell."""
        windows = []
        try:
            # PowerShell command to get visible windows with titles
            ps_command = '''
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                using System.Text;
                using System.Collections.Generic;
                
                public class WindowHelper {
                    [DllImport("user32.dll")]
                    private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                    
                    [DllImport("user32.dll")]
                    private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
                    
                    [DllImport("user32.dll")]
                    private static extern bool IsWindowVisible(IntPtr hWnd);
                    
                    [DllImport("user32.dll")]
                    private static extern int GetWindowTextLength(IntPtr hWnd);
                    
                    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                    
                    public static List GetWindows() {
                        List windows = new List();
                        EnumWindows((hWnd, lParam) => {
                            if (IsWindowVisible(hWnd)) {
                                int length = GetWindowTextLength(hWnd);
                                if (length > 0) {
                                    StringBuilder sb = new StringBuilder(length + 1);
                                    GetWindowText(hWnd, sb, sb.Capacity);
                                    string title = sb.ToString();
                                    if (!string.IsNullOrWhiteSpace(title)) {
                                        windows.Add(title);
                                    }
                                }
                            }
                            return true;
                        }, IntPtr.Zero);
                        return windows;
                    }
                }
"@
            [WindowHelper]::GetWindows() | ForEach-Object { Write-Output $_ }
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                seen_titles = set()
                for line in result.stdout.strip().split('\n'):
                    title = line.strip()
                    if title and title not in seen_titles:
                        # Skip system windows
                        skip_keywords = ['Program Manager', 'MSCTFIME', 'Default IME', 
                                       'Windows Input Experience', 'TextInputHost']
                        if not any(kw in title for kw in skip_keywords):
                            seen_titles.add(title)
                            windows.append({
                                'name': title[:60] + ('...' if len(title) > 60 else ''),
                                'id': title,
                                'full_title': title,
                                'type': 'window'
                            })
        except Exception as e:
            print(f"Error enumerating Windows windows: {e}")
        
        return windows
    
    def _get_linux_windows(self) -> List[Dict[str, str]]:
        """Get open windows on Linux using wmctrl or xdotool."""
        windows = []
        
        # Try wmctrl first
        try:
            result = subprocess.run(
                ['wmctrl', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            window_id = parts[0]
                            title = parts[3]
                            if title and title != 'N/A':
                                # Get window geometry
                                geometry = self._get_linux_window_geometry(window_id)
                                windows.append({
                                    'name': title[:60] + ('...' if len(title) > 60 else ''),
                                    'id': window_id,
                                    'full_title': title,
                                    'type': 'window',
                                    'geometry': geometry
                                })
                return windows
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"wmctrl error: {e}")
        
        # Fallback to xdotool
        try:
            result = subprocess.run(
                ['xdotool', 'search', '--name', ''],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                window_ids = result.stdout.strip().split('\n')
                for wid in window_ids[:30]:  # Limit to 30 windows
                    if wid:
                        try:
                            name_result = subprocess.run(
                                ['xdotool', 'getwindowname', wid],
                                capture_output=True,
                                text=True,
                                timeout=2
                            )
                            if name_result.returncode == 0:
                                title = name_result.stdout.strip()
                                if title:
                                    geometry = self._get_linux_window_geometry(wid)
                                    windows.append({
                                        'name': title[:60] + ('...' if len(title) > 60 else ''),
                                        'id': wid,
                                        'full_title': title,
                                        'type': 'window',
                                        'geometry': geometry
                                    })
                        except Exception:
                            pass
        except FileNotFoundError:
            print("Neither wmctrl nor xdotool found. Install with: sudo apt install wmctrl xdotool")
        except Exception as e:
            print(f"xdotool error: {e}")
        
        return windows
    
    def _get_linux_window_geometry(self, window_id: str) -> Dict[str, int]:
        """Get window geometry (position and size) on Linux."""
        geometry = {'x': 0, 'y': 0, 'width': 1920, 'height': 1080}
        
        try:
            result = subprocess.run(
                ['xwininfo', '-id', window_id],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Absolute upper-left X:' in line:
                        geometry['x'] = int(re.search(r':\s*(\d+)', line).group(1))
                    elif 'Absolute upper-left Y:' in line:
                        geometry['y'] = int(re.search(r':\s*(\d+)', line).group(1))
                    elif 'Width:' in line:
                        geometry['width'] = int(re.search(r':\s*(\d+)', line).group(1))
                    elif 'Height:' in line:
                        geometry['height'] = int(re.search(r':\s*(\d+)', line).group(1))
        except Exception as e:
            print(f"Error getting window geometry: {e}")
        
        return geometry


# =============================================================================
# DEVICE ENUMERATION
# =============================================================================

class DeviceEnumerator:
    """Class to enumerate available audio and video devices."""
    
    def __init__(self):
        self.os_type = OSDetector.get_os()
    
    def get_video_devices(self) -> List[Dict[str, str]]:
        """Get available video capture devices."""
        if self.os_type == 'windows':
            return self._get_windows_video_devices()
        elif self.os_type == 'linux':
            return self._get_linux_video_devices()
        return []
    
    def get_audio_devices(self) -> List[Dict[str, str]]:
        """Get available audio input devices (microphones)."""
        if self.os_type == 'windows':
            return self._get_windows_audio_devices()
        elif self.os_type == 'linux':
            return self._get_linux_audio_devices()
        return []
    
    def get_system_audio_devices(self) -> List[Dict[str, str]]:
        """Get available system audio (loopback) devices."""
        if self.os_type == 'windows':
            return self._get_windows_system_audio()
        elif self.os_type == 'linux':
            return self._get_linux_system_audio()
        return []
    
    # -------------------------------------------------------------------------
    # Windows Device Enumeration
    # -------------------------------------------------------------------------
    
    def _get_windows_video_devices(self) -> List[Dict[str, str]]:
        """Get Windows video devices. Uses gdigrab for desktop capture."""
        devices = [
            {'name': 'Full Desktop', 'id': 'desktop', 'type': 'gdigrab'}
        ]
        
        # Also try to list DirectShow video devices (webcams)
        try:
            dshow_devices = self._parse_dshow_devices('video')
            for dev in dshow_devices:
                devices.append({
                    'name': f"Camera: {dev}",
                    'id': dev,
                    'type': 'dshow_video'
                })
        except Exception:
            pass
        
        return devices
    
    def _get_windows_audio_devices(self) -> List[Dict[str, str]]:
        """Get Windows audio input devices using dshow."""
        devices = []
        try:
            dshow_devices = self._parse_dshow_devices('audio')
            for dev in dshow_devices:
                devices.append({
                    'name': dev,
                    'id': dev,
                    'type': 'dshow'
                })
        except Exception:
            # Fallback default
            devices.append({
                'name': 'Default Microphone',
                'id': 'Microphone',
                'type': 'dshow'
            })
        return devices
    
    def _get_windows_system_audio(self) -> List[Dict[str, str]]:
        """Get Windows system audio (loopback) devices."""
        devices = []
        try:
            dshow_devices = self._parse_dshow_devices('audio')
            for dev in dshow_devices:
                lower_name = dev.lower()
                # Look for stereo mix, loopback, or similar
                if any(term in lower_name for term in 
                       ['stereo mix', 'what u hear', 'loopback', 'wave out', 'mix']):
                    devices.append({
                        'name': f'{dev} (System Audio)',
                        'id': dev,
                        'type': 'dshow'
                    })
        except Exception:
            pass
        
        # Info about virtual audio cable
        if not devices:
            devices.append({
                'name': 'Stereo Mix (Enable in Sound Settings)',
                'id': 'Stereo Mix',
                'type': 'dshow'
            })
        
        return devices
    
    def _parse_dshow_devices(self, device_type: str) -> List[str]:
        """
        Parse DirectShow devices from FFmpeg output.
        
        Args:
            device_type: 'audio' or 'video'
        
        Returns:
            List of device names
        """
        devices = []
        try:
            result = subprocess.run(
                ['ffmpeg', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            output = result.stderr
            in_section = False
            target_section = f'DirectShow {device_type} devices'
            
            for line in output.split('\n'):
                line_lower = line.lower()
                
                # Check for section header
                if target_section.lower() in line_lower:
                    in_section = True
                    continue
                
                # Check for end of section
                if in_section and 'directshow' in line_lower and device_type not in line_lower:
                    break
                
                # Parse device names (they appear in quotes)
                if in_section:
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        device_name = match.group(1)
                        # Skip alternative names (start with @)
                        if not device_name.startswith('@'):
                            devices.append(device_name)
        
        except Exception as e:
            print(f"Error parsing dshow devices: {e}")
        
        return devices
    
    # -------------------------------------------------------------------------
    # Linux Device Enumeration
    # -------------------------------------------------------------------------
    
    def _get_linux_video_devices(self) -> List[Dict[str, str]]:
        """Get Linux video devices for x11grab."""
        devices = []
        display = os.environ.get('DISPLAY', ':0')
        
        # Try to get screen resolution using xdpyinfo
        try:
            result = subprocess.run(
                ['xdpyinfo'],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'dimensions:' in line:
                    match = re.search(r'(\d+x\d+)', line)
                    if match:
                        resolution = match.group(1)
                        devices.append({
                            'name': f'Full Desktop ({resolution})',
                            'id': display,
                            'type': 'x11grab',
                            'resolution': resolution
                        })
                        break
        except Exception:
            pass
        
        # Fallback if xdpyinfo fails
        if not devices:
            devices.append({
                'name': 'Full Desktop (Default)',
                'id': display,
                'type': 'x11grab',
                'resolution': '1920x1080'
            })
        
        return devices
    
    def _get_linux_audio_devices(self) -> List[Dict[str, str]]:
        """Get Linux audio input devices using PulseAudio."""
        devices = []
        try:
            result = subprocess.run(
                ['pactl', 'list', 'sources', 'short'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            source_id = parts[1]
                            # Filter out monitor sources (those are for system audio)
                            if '.monitor' not in source_id:
                                devices.append({
                                    'name': source_id,
                                    'id': source_id,
                                    'type': 'pulse'
                                })
        except Exception:
            pass
        
        if not devices:
            devices.append({
                'name': 'default',
                'id': 'default',
                'type': 'pulse'
            })
        
        return devices
    
    def _get_linux_system_audio(self) -> List[Dict[str, str]]:
        """Get Linux system audio (monitor) devices via PulseAudio."""
        devices = []
        try:
            result = subprocess.run(
                ['pactl', 'list', 'sources', 'short'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            source_id = parts[1]
                            # Monitor sources capture system audio output
                            if '.monitor' in source_id:
                                display_name = source_id.replace('.monitor', ' (System)')
                                devices.append({
                                    'name': display_name,
                                    'id': source_id,
                                    'type': 'pulse'
                                })
        except Exception:
            pass
        
        if not devices:
            devices.append({
                'name': 'System Audio (Default Monitor)',
                'id': '@DEFAULT_MONITOR@',
                'type': 'pulse'
            })
        
        return devices


# =============================================================================
# FFMPEG COMMAND BUILDER
# =============================================================================

class FFmpegCommandBuilder:
    """Class to build FFmpeg commands based on OS and user options."""
    
    def __init__(self):
        self.os_type = OSDetector.get_os()
    
    def build_ffmpeg_command(
        self,
        output_path: str,
        video_device: Dict[str, str],
        audio_device: Optional[Dict[str, str]] = None,
        system_audio_device: Optional[Dict[str, str]] = None,
        record_system_audio: bool = False,
        framerate: int = 30,
        video_codec: str = 'libx264',
        audio_codec: str = 'aac',
        quality: str = 'medium',
        capture_window: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """
        Build the complete FFmpeg command based on settings.
        
        Args:
            output_path: Path to save the output video
            video_device: Video capture device info
            audio_device: Microphone device info (optional)
            system_audio_device: System audio device info (optional)
            record_system_audio: Whether to record system audio
            framerate: Video frame rate
            video_codec: Video codec to use
            audio_codec: Audio codec to use
            quality: Quality preset ('low', 'medium', 'high', 'lossless')
            capture_window: Specific window to capture (optional)
        
        Returns:
            List of command arguments for subprocess
        """
        if self.os_type == 'windows':
            return self._build_windows_command(
                output_path, video_device, audio_device,
                system_audio_device, record_system_audio,
                framerate, video_codec, audio_codec, quality,
                capture_window
            )
        elif self.os_type == 'linux':
            return self._build_linux_command(
                output_path, video_device, audio_device,
                system_audio_device, record_system_audio,
                framerate, video_codec, audio_codec, quality,
                capture_window
            )
        else:
            raise RuntimeError(f"Unsupported OS: {self.os_type}")
    
    def _get_quality_settings(self, quality: str) -> Dict[str, str]:
        """Get encoding quality settings based on preset."""
        settings = {
            'low': {'crf': '28', 'preset': 'ultrafast'},
            'medium': {'crf': '23', 'preset': 'medium'},
            'high': {'crf': '18', 'preset': 'slow'},
            'lossless': {'crf': '0', 'preset': 'medium'}
        }
        return settings.get(quality, settings['medium'])
    
    def _build_windows_command(
        self,
        output_path: str,
        video_device: Dict[str, str],
        audio_device: Optional[Dict[str, str]],
        system_audio_device: Optional[Dict[str, str]],
        record_system_audio: bool,
        framerate: int,
        video_codec: str,
        audio_codec: str,
        quality: str,
        capture_window: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """Build FFmpeg command for Windows using gdigrab + dshow."""
        cmd = ['ffmpeg', '-y']  # -y to overwrite output
        
        quality_settings = self._get_quality_settings(quality)
        
        # === INPUT: Video ===
        if capture_window and capture_window.get('type') == 'window':
            # Capture specific window by title
            window_title = capture_window.get('full_title', capture_window.get('id', ''))
            cmd.extend([
                '-f', 'gdigrab',
                '-framerate', str(framerate),
                '-i', f'title={window_title}'
            ])
        elif video_device.get('type') == 'gdigrab':
            # Full desktop capture with gdigrab
            cmd.extend([
                '-f', 'gdigrab',
                '-framerate', str(framerate),
                '-i', 'desktop'
            ])
        else:
            # DirectShow camera
            cmd.extend([
                '-f', 'dshow',
                '-framerate', str(framerate),
                '-i', f'video={video_device["id"]}'
            ])
        
        # === INPUT: Audio sources ===
        audio_inputs = []
        input_idx = 1  # Video is input 0
        
        # Microphone input
        if audio_device:
            cmd.extend([
                '-f', 'dshow',
                '-i', f'audio={audio_device["id"]}'
            ])
            audio_inputs.append(f'{input_idx}:a')
            input_idx += 1
        
        # System audio input
        if record_system_audio and system_audio_device:
            cmd.extend([
                '-f', 'dshow',
                '-i', f'audio={system_audio_device["id"]}'
            ])
            audio_inputs.append(f'{input_idx}:a')
            input_idx += 1
        
        # === FILTER COMPLEX: Audio mixing ===
        if len(audio_inputs) > 1:
            # Mix multiple audio sources using amix filter
            filter_inputs = ''.join([f'[{i}]' for i in audio_inputs])
            cmd.extend([
                '-filter_complex',
                f'{filter_inputs}amix=inputs={len(audio_inputs)}:duration=longest:dropout_transition=2[aout]',
                '-map', '0:v',
                '-map', '[aout]'
            ])
        elif len(audio_inputs) == 1:
            # Single audio source, no mixing needed
            cmd.extend([
                '-map', '0:v',
                '-map', '1:a'
            ])
        else:
            # No audio
            cmd.extend(['-map', '0:v'])
        
        # === OUTPUT: Encoding settings ===
        cmd.extend([
            '-c:v', video_codec,
            '-crf', quality_settings['crf'],
            '-preset', quality_settings['preset'],
            '-pix_fmt', 'yuv420p'
        ])
        
        if audio_inputs:
            cmd.extend([
                '-c:a', audio_codec,
                '-b:a', '192k',
                '-ar', '44100'
            ])
        
        cmd.append(output_path)
        
        return cmd
    
    def _build_linux_command(
        self,
        output_path: str,
        video_device: Dict[str, str],
        audio_device: Optional[Dict[str, str]],
        system_audio_device: Optional[Dict[str, str]],
        record_system_audio: bool,
        framerate: int,
        video_codec: str,
        audio_codec: str,
        quality: str,
        capture_window: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """Build FFmpeg command for Linux using x11grab + pulse."""
        cmd = ['ffmpeg', '-y']
        
        quality_settings = self._get_quality_settings(quality)
        
        # === INPUT: Video (x11grab) ===
        display = os.environ.get('DISPLAY', ':0')
        
        if capture_window and capture_window.get('type') == 'window':
            # Capture specific window region
            geometry = capture_window.get('geometry', {})
            x = geometry.get('x', 0)
            y = geometry.get('y', 0)
            width = geometry.get('width', 1920)
            height = geometry.get('height', 1080)
            
            # Ensure dimensions are even (required by many codecs)
            width = width if width % 2 == 0 else width + 1
            height = height if height % 2 == 0 else height + 1
            
            cmd.extend([
                '-f', 'x11grab',
                '-framerate', str(framerate),
                '-video_size', f'{width}x{height}',
                '-i', f'{display}+{x},{y}'
            ])
        else:
            # Full desktop capture
            resolution = video_device.get('resolution', '1920x1080')
            cmd.extend([
                '-f', 'x11grab',
                '-framerate', str(framerate),
                '-video_size', resolution,
                '-i', f'{display}+0,0'
            ])
        
        # === INPUT: Audio sources ===
        audio_inputs = []
        input_idx = 1
        
        # Microphone input via PulseAudio
        if audio_device:
            cmd.extend([
                '-f', 'pulse',
                '-i', audio_device['id']
            ])
            audio_inputs.append(f'{input_idx}:a')
            input_idx += 1
        
        # System audio input via PulseAudio monitor
        if record_system_audio and system_audio_device:
            cmd.extend([
                '-f', 'pulse',
                '-i', system_audio_device['id']
            ])
            audio_inputs.append(f'{input_idx}:a')
            input_idx += 1
        
        # === FILTER COMPLEX: Audio mixing ===
        if len(audio_inputs) > 1:
            filter_inputs = ''.join([f'[{i}]' for i in audio_inputs])
            cmd.extend([
                '-filter_complex',
                f'{filter_inputs}amix=inputs={len(audio_inputs)}:duration=longest:dropout_transition=2[aout]',
                '-map', '0:v',
                '-map', '[aout]'
            ])
        elif len(audio_inputs) == 1:
            cmd.extend([
                '-map', '0:v',
                '-map', '1:a'
            ])
        else:
            cmd.extend(['-map', '0:v'])
        
        # === OUTPUT: Encoding settings ===
        cmd.extend([
            '-c:v', video_codec,
            '-crf', quality_settings['crf'],
            '-preset', quality_settings['preset'],
            '-pix_fmt', 'yuv420p'
        ])
        
        if audio_inputs:
            cmd.extend([
                '-c:a', audio_codec,
                '-b:a', '192k',
                '-ar', '44100'
            ])
        
        cmd.append(output_path)
        
        return cmd


# =============================================================================
# RECORDING THREAD (ASYNC)
# =============================================================================

class RecordingThread(QThread):
    """
    QThread for handling FFmpeg recording process asynchronously.
    This prevents the GUI from freezing during recording.
    """
    
    # Signals to communicate with main thread
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    recording_error = pyqtSignal(str)
    duration_updated = pyqtSignal(int)  # Duration in seconds
    
    def __init__(self, command: List[str]):
        super().__init__()
        self.command = command
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.start_time = None
    
    def run(self):
        """Execute the recording process."""
        try:
            # Platform-specific process creation flags
            creationflags = 0
            if OSDetector.is_windows():
                creationflags = subprocess.CREATE_NO_WINDOW
            
            # Start FFmpeg process
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags
            )
            
            self.is_running = True
            self.start_time = datetime.now()
            self.recording_started.emit()
            
            # Monitor loop - update duration every second
            while self.is_running and self.process.poll() is None:
                if self.start_time:
                    elapsed = (datetime.now() - self.start_time).seconds
                    self.duration_updated.emit(elapsed)
                self.msleep(1000)
            
            # Wait for process to complete
            if self.process:
                self.process.wait()
            
            self.recording_stopped.emit()
            
        except Exception as e:
            self.recording_error.emit(str(e))
        finally:
            self.is_running = False
    
    def stop_recording(self):
        """Stop the recording gracefully by sending 'q' to FFmpeg."""
        self.is_running = False
        if self.process:
            try:
                # Send 'q' key to FFmpeg for graceful shutdown
                self.process.stdin.write(b'q')
                self.process.stdin.flush()
                
                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force terminate if it doesn't respond
                    self.process.terminate()
                    self.process.wait(timeout=2)
            except Exception:
                # Last resort: kill the process
                try:
                    self.process.kill()
                except Exception:
                    pass


# =============================================================================
# MAIN APPLICATION WINDOW
# =============================================================================

class ScreenRecorderApp(QMainWindow):
    """Main application window for the Screen Recorder."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize helper classes
        self.device_enumerator = DeviceEnumerator()
        self.window_enumerator = WindowEnumerator()
        self.command_builder = FFmpegCommandBuilder()
        self.recording_thread: Optional[RecordingThread] = None
        self.is_recording = False
        
        # Device storage
        self.video_devices = []
        self.audio_devices = []
        self.system_audio_devices = []
        self.open_windows = []
        
        # Setup UI
        self._init_ui()
        self._apply_dark_theme()
        
        # Check dependencies
        self._check_dependencies()
        
        # Load devices
        self._refresh_devices()
        self._refresh_windows()
    
    def _init_ui(self):
        """Initialize the user interface components."""
        self.setWindowTitle("🎬 Screen Recorder Pro")
        self.setMinimumSize(580, 620)
        self.setMaximumSize(700, 750)
        
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        
        # --- Title ---
        title_label = QLabel("🎬 Screen Recorder Pro")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # --- OS Info ---
        os_info = f"Platform: {platform.system()} {platform.release()}"
        os_label = QLabel(os_info)
        os_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        os_label.setStyleSheet("color: #888; font-size: 12px;")
        main_layout.addWidget(os_label)
        
        # --- Capture Mode Selection ---
        capture_group = QGroupBox("🎯 Capture Mode")
        capture_layout = QVBoxLayout(capture_group)
        
        # Radio buttons for capture mode
        self.capture_mode_group = QButtonGroup(self)
        
        mode_row = QHBoxLayout()
        self.desktop_radio = QRadioButton("🖥️ Full Desktop")
        self.desktop_radio.setChecked(True)
        self.desktop_radio.toggled.connect(self._on_capture_mode_changed)
        self.capture_mode_group.addButton(self.desktop_radio)
        mode_row.addWidget(self.desktop_radio)
        
        self.window_radio = QRadioButton("🪟 Specific Window/Tab")
        self.window_radio.toggled.connect(self._on_capture_mode_changed)
        self.capture_mode_group.addButton(self.window_radio)
        mode_row.addWidget(self.window_radio)
        
        capture_layout.addLayout(mode_row)
        
        # Window selection dropdown (initially hidden)
        window_row = QHBoxLayout()
        self.window_label = QLabel("Select Window:")
        self.window_label.setVisible(False)
        window_row.addWidget(self.window_label)
        
        self.window_combo = QComboBox()
        self.window_combo.setMinimumWidth(320)
        self.window_combo.setVisible(False)
        window_row.addWidget(self.window_combo)
        
        self.refresh_windows_btn = QPushButton("🔄")
        self.refresh_windows_btn.setFixedWidth(40)
        self.refresh_windows_btn.setToolTip("Refresh window list")
        self.refresh_windows_btn.clicked.connect(self._refresh_windows)
        self.refresh_windows_btn.setVisible(False)
        window_row.addWidget(self.refresh_windows_btn)
        
        capture_layout.addLayout(window_row)
        
        main_layout.addWidget(capture_group)
        
        # --- Video Settings Group ---
        video_group = QGroupBox("📹 Video Source (for Full Desktop)")
        video_layout = QGridLayout(video_group)
        
        video_layout.addWidget(QLabel("Screen/Display:"), 0, 0)
        self.video_combo = QComboBox()
        self.video_combo.setMinimumWidth(320)
        video_layout.addWidget(self.video_combo, 0, 1)
        
        main_layout.addWidget(video_group)
        self.video_group = video_group
        
        # --- Audio Settings Group ---
        audio_group = QGroupBox("🎤 Audio Settings")
        audio_layout = QGridLayout(audio_group)
        
        audio_layout.addWidget(QLabel("Microphone:"), 0, 0)
        self.audio_combo = QComboBox()
        self.audio_combo.setMinimumWidth(320)
        audio_layout.addWidget(self.audio_combo, 0, 1)
        
        self.system_audio_checkbox = QCheckBox("🔊 Record System Audio")
        self.system_audio_checkbox.setToolTip(
            "Capture desktop/system audio (what you hear through speakers)"
        )
        audio_layout.addWidget(self.system_audio_checkbox, 1, 0, 1, 2)
        
        audio_layout.addWidget(QLabel("System Audio Source:"), 2, 0)
        self.system_audio_combo = QComboBox()
        self.system_audio_combo.setEnabled(False)
        audio_layout.addWidget(self.system_audio_combo, 2, 1)
        
        # Connect checkbox to enable/disable system audio dropdown
        self.system_audio_checkbox.toggled.connect(
            self.system_audio_combo.setEnabled
        )
        
        main_layout.addWidget(audio_group)
        
        # --- Recording Duration Display ---
        self.duration_label = QLabel("⏱️ Duration: 00:00:00")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        self.duration_label.setStyleSheet("color: #4CAF50;")
        main_layout.addWidget(self.duration_label)
        
        # --- Control Buttons ---
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh Devices")
        self.refresh_btn.clicked.connect(self._refresh_all)
        button_layout.addWidget(self.refresh_btn)
        
        self.record_btn = QPushButton("⏺️ Start Recording")
        self.record_btn.setMinimumHeight(55)
        self.record_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.record_btn.clicked.connect(self._toggle_recording)
        button_layout.addWidget(self.record_btn)
        
        main_layout.addLayout(button_layout)
        
        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _on_capture_mode_changed(self, checked: bool):
        """Handle capture mode radio button changes."""
        is_window_mode = self.window_radio.isChecked()
        
        # Show/hide window selection controls
        self.window_label.setVisible(is_window_mode)
        self.window_combo.setVisible(is_window_mode)
        self.refresh_windows_btn.setVisible(is_window_mode)
        
        # Show/hide video source (only for desktop mode)
        self.video_group.setVisible(not is_window_mode)
        
        if is_window_mode:
            self._refresh_windows()
    
    def _apply_dark_theme(self):
        """Apply a modern dark theme to the application."""
        dark_palette = QPalette()
        
        # Define colors
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        
        self.setPalette(dark_palette)
        
        # Additional stylesheet for fine-tuned styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #444;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #2d2d2d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: #64B5F6;
            }
            QComboBox {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 8px 12px;
                min-height: 22px;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #64B5F6;
            }
            QComboBox:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QPushButton {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border: 1px solid #64B5F6;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QCheckBox {
                spacing: 10px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 1px solid #555;
                background-color: #3d3d3d;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 1px solid #4CAF50;
            }
            QRadioButton {
                spacing: 8px;
                font-size: 12px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #555;
                background-color: #3d3d3d;
            }
            QRadioButton::indicator:checked {
                background-color: #2196F3;
                border: 2px solid #2196F3;
            }
            QStatusBar {
                background-color: #252525;
                color: #888;
                font-size: 11px;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
        """)
    
    def _check_dependencies(self):
        """Check if FFmpeg is installed and accessible."""
        is_installed, message = FFmpegChecker.check_ffmpeg_installed()
        if not is_installed:
            QMessageBox.critical(
                self,
                "FFmpeg Not Found",
                f"{message}\n\nPlease install FFmpeg and ensure it's in your system PATH.\n\n"
                "Windows: Download from https://ffmpeg.org/download.html\n"
                "Linux: sudo apt install ffmpeg"
            )
            self.record_btn.setEnabled(False)
        else:
            self.status_bar.showMessage(f"✓ {message[:60]}...")
    
    def _refresh_all(self):
        """Refresh both devices and windows."""
        self._refresh_devices()
        self._refresh_windows()
    
    def _refresh_devices(self):
        """Refresh all device dropdown lists."""
        self.status_bar.showMessage("🔄 Refreshing devices...")
        
        # Clear existing items
        self.video_combo.clear()
        self.audio_combo.clear()
        self.system_audio_combo.clear()
        
        # Enumerate video devices
        self.video_devices = self.device_enumerator.get_video_devices()
        for device in self.video_devices:
            self.video_combo.addItem(device['name'])
        
        # Enumerate audio (microphone) devices
        self.audio_devices = self.device_enumerator.get_audio_devices()
        self.audio_combo.addItem("🚫 None (No Microphone)")
        for device in self.audio_devices:
            self.audio_combo.addItem(f"🎤 {device['name']}")
        
        # Enumerate system audio devices
        self.system_audio_devices = self.device_enumerator.get_system_audio_devices()
        for device in self.system_audio_devices:
            self.system_audio_combo.addItem(f"🔊 {device['name']}")
        
        self.status_bar.showMessage(
            f"✓ Found: {len(self.video_devices)} video, "
            f"{len(self.audio_devices)} mic, "
            f"{len(self.system_audio_devices)} system audio"
        )
    
    def _refresh_windows(self):
        """Refresh the open windows list."""
        self.status_bar.showMessage("🔄 Scanning open windows...")
        
        self.window_combo.clear()
        self.open_windows = self.window_enumerator.get_open_windows()
        
        if self.open_windows:
            for window in self.open_windows:
                self.window_combo.addItem(f"🪟 {window['name']}")
            self.status_bar.showMessage(f"✓ Found {len(self.open_windows)} open windows")
        else:
            self.window_combo.addItem("No windows found")
            self.status_bar.showMessage("⚠️ No capturable windows found")
    
    def _get_output_path(self) -> Optional[str]:
        """Open file dialog to get output file path."""
        default_name = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        videos_dir = Path.home() / "Videos"
        
        # Create Videos directory if it doesn't exist
        videos_dir.mkdir(exist_ok=True)
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Recording As",
            str(videos_dir / default_name),
            "MP4 Video (*.mp4);;MKV Video (*.mkv);;AVI Video (*.avi);;All Files (*)"
        )
        
        return file_path if file_path else None
    
    def _toggle_recording(self):
        """Toggle between start and stop recording."""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start the screen recording."""
        # Get output path from user
        output_path = self._get_output_path()
        if not output_path:
            return
        
        # Determine capture mode and get relevant device
        capture_window = None
        video_device = None
        
        if self.window_radio.isChecked():
            # Window capture mode
            window_idx = self.window_combo.currentIndex()
            if window_idx < 0 or window_idx >= len(self.open_windows):
                QMessageBox.warning(self, "Error", "Please select a window to capture.")
                return
            capture_window = self.open_windows[window_idx]
            # Use a dummy video device
            video_device = {'type': 'x11grab', 'id': ':0', 'resolution': '1920x1080'}
        else:
            # Full desktop mode
            video_idx = self.video_combo.currentIndex()
            if video_idx < 0 or video_idx >= len(self.video_devices):
                QMessageBox.warning(self, "Error", "Please select a video device.")
                return
            video_device = self.video_devices[video_idx]
        
        # Get audio settings
        audio_idx = self.audio_combo.currentIndex() - 1  # Subtract 1 for "None" option
        system_audio_idx = self.system_audio_combo.currentIndex()
        
        audio_device = self.audio_devices[audio_idx] if audio_idx >= 0 else None
        system_audio_device = (
            self.system_audio_devices[system_audio_idx]
            if self.system_audio_checkbox.isChecked() and system_audio_idx >= 0
            else None
        )
        
        try:
            # Build the FFmpeg command
            command = self.command_builder.build_ffmpeg_command(
                output_path=output_path,
                video_device=video_device,
                audio_device=audio_device,
                system_audio_device=system_audio_device,
                record_system_audio=self.system_audio_checkbox.isChecked(),
                capture_window=capture_window
            )
            
            # Debug: Print command to console
            print("=" * 60)
            print("FFmpeg Command:")
            print(' '.join(command))
            print("=" * 60)
            
            # Create and start recording thread
            self.recording_thread = RecordingThread(command)
            self.recording_thread.recording_started.connect(self._on_recording_started)
            self.recording_thread.recording_stopped.connect(self._on_recording_stopped)
            self.recording_thread.recording_error.connect(self._on_recording_error)
            self.recording_thread.duration_updated.connect(self._on_duration_updated)
            self.recording_thread.start()
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error", 
                f"Failed to start recording:\n{str(e)}"
            )
    
    def _stop_recording(self):
        """Stop the current recording."""
        if self.recording_thread:
            self.status_bar.showMessage("⏹️ Stopping recording...")
            self.recording_thread.stop_recording()
    
    def _on_recording_started(self):
        """Handle recording started signal."""
        self.is_recording = True
        self.record_btn.setText("⏹️ Stop Recording")
        self.record_btn.setStyleSheet(
            "background-color: #c0392b; color: white; "
            "border: 2px solid #e74c3c;"
        )
        self.duration_label.setStyleSheet("color: #f44336;")
        
        # Disable controls during recording
        self.refresh_btn.setEnabled(False)
        self.video_combo.setEnabled(False)
        self.audio_combo.setEnabled(False)
        self.system_audio_checkbox.setEnabled(False)
        self.system_audio_combo.setEnabled(False)
        self.desktop_radio.setEnabled(False)
        self.window_radio.setEnabled(False)
        self.window_combo.setEnabled(False)
        self.refresh_windows_btn.setEnabled(False)
        
        mode = "Window" if self.window_radio.isChecked() else "Desktop"
        self.status_bar.showMessage(f"🔴 Recording {mode} in progress...")
    
    def _on_recording_stopped(self):
        """Handle recording stopped signal."""
        self.is_recording = False
        self.record_btn.setText("⏺️ Start Recording")
        self.record_btn.setStyleSheet("")
        self.duration_label.setText("⏱️ Duration: 00:00:00")
        self.duration_label.setStyleSheet("color: #4CAF50;")
        
        # Re-enable controls
        self.refresh_btn.setEnabled(True)
        self.video_combo.setEnabled(True)
        self.audio_combo.setEnabled(True)
        self.system_audio_checkbox.setEnabled(True)
        self.system_audio_combo.setEnabled(self.system_audio_checkbox.isChecked())
        self.desktop_radio.setEnabled(True)
        self.window_radio.setEnabled(True)
        self.window_combo.setEnabled(True)
        self.refresh_windows_btn.setEnabled(True)
        
        self.status_bar.showMessage("✅ Recording saved successfully!")
        
        QMessageBox.information(
            self, "Recording Complete",
            "Your recording has been saved successfully!"
        )
    
    def _on_recording_error(self, error_message: str):
        """Handle recording error signal."""
        self.is_recording = False
        self.record_btn.setText("⏺️ Start Recording")
        self.record_btn.setStyleSheet("")
        self.duration_label.setText("⏱️ Duration: 00:00:00")
        self.duration_label.setStyleSheet("color: #4CAF50;")
        
        # Re-enable controls
        self.refresh_btn.setEnabled(True)
        self.video_combo.setEnabled(True)
        self.audio_combo.setEnabled(True)
        self.system_audio_checkbox.setEnabled(True)
        self.system_audio_combo.setEnabled(self.system_audio_checkbox.isChecked())
        self.desktop_radio.setEnabled(True)
        self.window_radio.setEnabled(True)
        self.window_combo.setEnabled(True)
        self.refresh_windows_btn.setEnabled(True)
        
        QMessageBox.critical(
            self, "Recording Error",
            f"An error occurred during recording:\n\n{error_message}"
        )
        self.status_bar.showMessage("❌ Recording failed!")
    
    def _on_duration_updated(self, seconds: int):
        """Update the duration display."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        self.duration_label.setText(
            f"⏱️ Duration: {hours:02d}:{minutes:02d}:{secs:02d}"
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_recording:
            reply = QMessageBox.question(
                self,
                "Recording in Progress",
                "A recording is currently in progress.\n\n"
                "Do you want to stop the recording and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_recording()
                if self.recording_thread:
                    self.recording_thread.wait(5000)  # Wait up to 5 seconds
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the application."""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Screen Recorder Pro")
    app.setStyle("Fusion")  # Use Fusion style for cross-platform consistency
    
    # Create and show main window
    window = ScreenRecorderApp()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
