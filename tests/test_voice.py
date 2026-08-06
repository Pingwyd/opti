"""Tests for voice input config, helpers, and gating."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import config
from config import DEFAULT_VOICE_PTT_SHORTCUT
from settings_ui import apply_settings_values, build_settings_values
from voice import (
    VoiceTranscriber,
    compute_rms,
    missing_voice_deps_message,
    voice_deps_available,
)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    return config_path


def _base_settings_kwargs(**overrides):
    defaults = {
        "provider": "gemini",
        "api_key_input": "",
        "hotkey": "Ctrl+Shift+Space",
        "hotkey_collapse": config.DEFAULT_HOTKEY_COLLAPSE,
        "model": "gemini-3.5-flash",
        "model_fast": "gemini-3.1-flash-lite",
        "mode": "thorough",
        "persist_draft": True,
        "save_history": True,
        "exclude_sensitive": False,
        "history_limit": 50,
        "start_with_windows": False,
        "start_minimized_to_tray": True,
        "check_updates_on_launch": False,
        "shortcut_collapse": config.DEFAULT_SHORTCUT_COLLAPSE,
        "shortcut_hide_tray": config.DEFAULT_SHORTCUT_HIDE_TRAY,
        "shortcut_private": config.DEFAULT_SHORTCUT_PRIVATE,
        "auto_copy_clipboard": True,
        "voice_enabled": False,
        "voice_transcription_mode": "local",
        "voice_recording_mode": "push_to_talk",
        "voice_model_size": "base",
        "voice_toggle_max_seconds": 60,
        "voice_ptt_shortcut": DEFAULT_VOICE_PTT_SHORTCUT,
    }
    defaults.update(overrides)
    return defaults


def test_voice_config_defaults(isolated_config):
    cfg = config.load_config()
    assert cfg["voice_enabled"] is False
    assert cfg["voice_transcription_mode"] == "local"
    assert cfg["voice_recording_mode"] == "push_to_talk"
    assert cfg["voice_model_size"] == "base"
    assert cfg["voice_toggle_max_seconds"] == 60
    assert cfg["voice_ptt_shortcut"] == DEFAULT_VOICE_PTT_SHORTCUT


def test_voice_settings_round_trip(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(
            voice_enabled=True,
            voice_transcription_mode="local",
            voice_recording_mode="toggle",
            voice_model_size="small",
            voice_toggle_max_seconds=90,
            voice_ptt_shortcut="Ctrl+Space",
        )
    )
    assert apply_settings_values(values) is None
    cfg = config.load_config()
    assert cfg["voice_enabled"] is True
    assert cfg["voice_recording_mode"] == "toggle"
    assert cfg["voice_model_size"] == "small"
    assert cfg["voice_toggle_max_seconds"] == 90
    assert config.get_voice_ptt_shortcut() == "Ctrl+Space"


def test_private_mode_forces_local_transcription(isolated_config):
    config.load_config()
    values = build_settings_values(
        **_base_settings_kwargs(voice_transcription_mode="cloud")
    )
    apply_settings_values(values)
    assert config.get_voice_transcription_mode(private_mode=True) == "local"


def test_compute_rms_silence_and_signal():
    np = pytest.importorskip("numpy")
    assert compute_rms(np.array([], dtype=np.float32)) == 0.0
    assert compute_rms(np.zeros(128, dtype=np.float32)) == 0.0
    samples = np.full(128, 0.5, dtype=np.float32)
    rms = compute_rms(samples)
    assert 0.49 < rms < 0.51


def test_compute_rms_none():
    assert compute_rms(None) == 0.0


def test_voice_deps_available_without_optional_packages(monkeypatch):
    monkeypatch.setattr("voice.NUMPY_AVAILABLE", False)
    monkeypatch.setattr("voice.SOUNDDEVICE_AVAILABLE", False)
    monkeypatch.setattr("voice.FASTER_WHISPER_AVAILABLE", False)
    assert voice_deps_available() is False
    message = missing_voice_deps_message()
    assert "numpy" in message
    assert "sounddevice" in message
    assert "faster-whisper" in message


def test_voice_transcriber_transcribe_mock():
    np = pytest.importorskip("numpy")
    mock_model = MagicMock()
    segment = MagicMock()
    segment.text = " hello world "
    mock_model.transcribe.return_value = ([segment], None)

    with patch("voice.WhisperModel", return_value=mock_model), patch(
        "voice.FASTER_WHISPER_AVAILABLE", True
    ), patch("voice.NUMPY_AVAILABLE", True):
        transcriber = VoiceTranscriber(model_size="base")
        audio = np.zeros(16000, dtype=np.float32)
        assert transcriber.transcribe(audio) == "hello world"
        mock_model.transcribe.assert_called_once()


def test_voice_transcriber_empty_audio():
    np = pytest.importorskip("numpy")
    with patch("voice.FASTER_WHISPER_AVAILABLE", True), patch(
        "voice.NUMPY_AVAILABLE", True
    ):
        transcriber = VoiceTranscriber(model_size="base")
        assert transcriber.transcribe(np.array([], dtype=np.float32)) == ""


def test_voice_enabled_getters(isolated_config):
    config.load_config()
    assert config.get_voice_enabled() is False
    assert config.get_voice_recording_mode() == "push_to_talk"
    assert config.get_voice_model_size() == "base"
    assert config.get_voice_toggle_max_seconds() == 60

    values = build_settings_values(**_base_settings_kwargs(voice_enabled=True))
    apply_settings_values(values)
    assert config.get_voice_enabled() is True


@pytest.mark.skipif(
    not voice_deps_available(),
    reason="Optional voice dependencies not installed",
)
def test_audio_recorder_integration_requires_microphone():
    pytest.importorskip("sounddevice")
    from voice import AudioRecorder

    recorder = AudioRecorder()
    recorder.start()
    assert recorder.is_recording()
    audio = recorder.stop()
    assert audio is not None
