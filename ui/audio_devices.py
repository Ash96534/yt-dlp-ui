"""Multi-output audio support for YT-DLP WebUI.

Enumerates available audio output devices and manages simultaneous playback
to multiple outputs (e.g., Bluetooth speaker + laptop speakers + headphones).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtMultimedia import QAudioDevice, QAudioOutput, QMediaPlayer, QMediaDevices
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QObject, QUrl, QTimer, pyqtSignal


class AudioOutputDevice:
    """Represents a single audio output device."""

    def __init__(self, device: QAudioDevice):
        self.device = device
        self.name = device.description()
        self.id = device.id()
        self.is_default = device == QMediaDevices.defaultAudioOutput()

    def __repr__(self) -> str:
        return f"AudioOutputDevice(name={self.name!r}, default={self.is_default})"


class MultiOutputManager(QObject):
    """Manages playback to multiple audio output devices simultaneously.

    Creates one QMediaPlayer + QAudioOutput pair per selected output device
    and synchronizes playback state across all of them.
    """

    # Signals for UI integration
    playbackStateChanged = pyqtSignal(QMediaPlayer.PlaybackState)
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(QMediaPlayer.MediaStatus)

    def __init__(self, video_widget=None, parent=None):
        super().__init__(parent)
        self.video_widget = video_widget
        self.parent = parent
        self._outputs: Dict[str, Dict[str, Any]] = {}  # device_id -> {device, player, audio_output, volume}
        self._active_device_ids: List[str] = []
        self._current_source: Optional[str] = None
        self._volume: float = 0.7

    # ------------------------------------------------------------------ #
    # Device enumeration
    # ------------------------------------------------------------------ #
    @staticmethod
    def available_output_devices() -> List[AudioOutputDevice]:
        """Return all available audio output devices."""
        devices = []
        for dev in QMediaDevices.audioOutputs():
            devices.append(AudioOutputDevice(dev))
        return devices

    @staticmethod
    def default_output_device() -> Optional[AudioOutputDevice]:
        """Return the default output device."""
        dev = QMediaDevices.defaultAudioOutput()
        if dev is not None:
            return AudioOutputDevice(dev)
        return None

    # ------------------------------------------------------------------ #
    # Output management
    # ------------------------------------------------------------------ #
    def set_outputs(self, device_ids: List[str]) -> None:
        """Set which output devices to use for playback."""
        # Stop and clean up removed outputs
        for did in list(self._outputs.keys()):
            if did not in device_ids:
                self._stop_output(did)

        # Add new outputs
        for did in device_ids:
            if did not in self._outputs:
                self._start_output(did)

        self._active_device_ids = list(device_ids)

        # If we have a current source, load it into new outputs
        if self._current_source and self._active_device_ids:
            for did in self._active_device_ids:
                if did in self._outputs:
                    player = self._outputs[did]["player"]
                    if player.source().isEmpty() or player.source().toString() != self._current_source:
                        player.setSource(QUrl.fromLocalFile(self._current_source))
                        if self.player_state() == QMediaPlayer.PlaybackState.PlayingState:
                            player.play()

    def _start_output(self, device_id: str) -> None:
        """Start audio output for a specific device."""
        dev = None
        for d in QMediaDevices.audioOutputs():
            if d.id() == device_id:
                dev = d
                break
        if dev is None:
            return

        player = QMediaPlayer()
        audio_output = QAudioOutput(dev)
        audio_output.setVolume(self._volume)
        player.setAudioOutput(audio_output)

        if self.video_widget:
            player.setVideoOutput(self.video_widget)

        # Forward player signals to MultiOutputManager signals
        player.playbackStateChanged.connect(self.playbackStateChanged.emit)
        player.positionChanged.connect(self.positionChanged.emit)
        player.durationChanged.connect(self.durationChanged.emit)
        player.mediaStatusChanged.connect(self.mediaStatusChanged.emit)

        if self._current_source:
            player.setSource(QUrl.fromLocalFile(self._current_source))

        self._outputs[device_id] = {
            "device": AudioOutputDevice(dev),
            "player": player,
            "audio_output": audio_output,
            "volume": self._volume,
        }

    def _stop_output(self, device_id: str) -> None:
        """Stop and clean up output for a device."""
        if device_id in self._outputs:
            entry = self._outputs[device_id]
            player = entry["player"]
            player.stop()
            player.setAudioOutput(None)
            del self._outputs[device_id]

    # ------------------------------------------------------------------ #
    # Playback control
    # ------------------------------------------------------------------ #
    def set_source(self, filepath: str) -> None:
        """Load a media file into all active outputs."""
        self._current_source = filepath
        for did, entry in self._outputs.items():
            entry["player"].setSource(QUrl.fromLocalFile(filepath))
        self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadingMedia)

    def play(self) -> None:
        """Start playback on all active outputs."""
        for entry in self._outputs.values():
            entry["player"].play()
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)

    def pause(self) -> None:
        """Pause playback on all active outputs."""
        for entry in self._outputs.values():
            entry["player"].pause()
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PausedState)

    def stop(self) -> None:
        """Stop playback on all active outputs."""
        for entry in self._outputs.values():
            entry["player"].stop()
        self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)

    def player_state(self) -> QMediaPlayer.PlaybackState:
        """Return the playback state (assumes all outputs are synced)."""
        if self._outputs:
            first = next(iter(self._outputs.values()))
            return first["player"].playbackState()
        return QMediaPlayer.PlaybackState.StoppedState

    def position(self) -> int:
        """Return current playback position in ms."""
        if self._outputs:
            first = next(iter(self._outputs.values()))
            return first["player"].position()
        return 0

    def duration(self) -> int:
        """Return total duration in ms."""
        if self._outputs:
            first = next(iter(self._outputs.values()))
            return first["player"].duration()
        return 0

    def set_position(self, ms: int) -> None:
        """Seek all outputs to position ms."""
        for entry in self._outputs.values():
            entry["player"].setPosition(ms)
        self.positionChanged.emit(ms)

    def set_volume(self, volume: float) -> None:
        """Set volume (0.0-1.0) for all outputs."""
        self._volume = max(0.0, min(1.0, volume))
        for entry in self._outputs.values():
            entry["audio_output"].setVolume(self._volume)
            entry["volume"] = self._volume

    def set_output_volume(self, device_id: str, volume: float) -> None:
        """Set volume for a specific output device."""
        if device_id in self._outputs:
            vol = max(0.0, min(1.0, volume))
            self._outputs[device_id]["audio_output"].setVolume(vol)
            self._outputs[device_id]["volume"] = vol

    def is_playing(self) -> bool:
        return self.player_state() == QMediaPlayer.PlaybackState.PlayingState

    def get_output_volumes(self) -> Dict[str, float]:
        """Return {device_id: volume} for all active outputs."""
        return {did: entry["volume"] for did, entry in self._outputs.items()}

    def get_active_device_names(self) -> List[str]:
        """Return human-readable names of active output devices."""
        return [
            self._outputs[did]["device"].name
            for did in self._active_device_ids
            if did in self._outputs
        ]

    def cleanup(self) -> None:
        """Stop and release all outputs."""
        for did in list(self._outputs.keys()):
            self._stop_output(did)
        self._outputs.clear()
        self._active_device_ids.clear()
