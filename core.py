from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import csv, json


@dataclass
class Message:
    seq: int
    timestamp: str
    source: str
    destination: str
    event: str
    payload: Dict[str, Any]


class TraceLogger:
    """Collects Android-style logs and a structured message trace."""
    def __init__(self) -> None:
        self.messages: List[Message] = []
        self.logs: List[str] = []
        self._seq = 0

    def emit(self, source: str, destination: str, event: str, payload: Optional[Dict[str, Any]] = None,
             level: str = "I") -> Message:
        self._seq += 1
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        payload = payload or {}
        msg = Message(self._seq, stamp, source, destination, event, payload)
        self.messages.append(msg)
        payload_text = " ".join(f"{k}={v}" for k, v in payload.items())
        line = f"{stamp} {level}/{source}: -> {destination} | {event}"
        if payload_text:
            line += f" | {payload_text}"
        self.logs.append(line)
        return msg


class AudioHAL:
    def __init__(self, trace: TraceLogger):
        self.trace = trace
        self.state = "CLOSED"
        self.volume = 0.70

    def open(self, sample_rate: int = 48000, channels: int = 2) -> None:
        self.state = "OPEN"
        self.trace.emit("AudioHAL", "DSP/Amplifier", "HAL_OPEN",
                        {"sample_rate": sample_rate, "channels": channels})

    def write(self, frames: int) -> None:
        if self.state != "OPEN":
            raise RuntimeError("AudioHAL.write() called while HAL is not OPEN")
        self.trace.emit("AudioHAL", "DSP/Amplifier", "HAL_WRITE", {"frames": frames})

    def set_volume(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        self.volume = value
        self.trace.emit("AudioHAL", "DSP/Amplifier", "HAL_SET_VOLUME", {"volume": value})

    def flush(self) -> None:
        self.trace.emit("AudioHAL", "DSP/Amplifier", "HAL_FLUSH")

    def standby(self) -> None:
        self.state = "STANDBY"
        self.trace.emit("AudioHAL", "DSP/Amplifier", "HAL_STANDBY")

    def close(self) -> None:
        self.state = "CLOSED"
        self.trace.emit("AudioHAL", "DSP/Amplifier", "HAL_CLOSE")


class AudioFlinger:
    """Simplified mixer/routing stage between AudioService and Audio HAL."""
    def __init__(self, trace: TraceLogger, hal: AudioHAL):
        self.trace = trace
        self.hal = hal

    def start_output(self) -> None:
        self.trace.emit("AudioFlinger", "AudioHAL", "OPEN_OUTPUT")
        self.hal.open()

    def write_audio(self, frames: int = 1024) -> None:
        self.trace.emit("AudioFlinger", "AudioHAL", "WRITE_MIXED_AUDIO", {"frames": frames})
        self.hal.write(frames)

    def pause_output(self) -> None:
        self.trace.emit("AudioFlinger", "AudioHAL", "PAUSE_OUTPUT")
        self.hal.flush()

    def resume_output(self) -> None:
        self.trace.emit("AudioFlinger", "AudioHAL", "RESUME_OUTPUT")


class AudioService:
    def __init__(self, trace: TraceLogger, flinger: AudioFlinger):
        self.trace = trace
        self.flinger = flinger
        self.focus_holder: Optional[str] = None

    def request_focus(self, owner: str) -> bool:
        self.focus_holder = owner
        self.trace.emit("AudioService", "AudioFlinger", "AUDIO_FOCUS_GRANTED", {"owner": owner})
        return True

    def release_focus(self, owner: str) -> None:
        if self.focus_holder == owner:
            self.focus_holder = None
        self.trace.emit("AudioService", "AudioFlinger", "AUDIO_FOCUS_RELEASED", {"owner": owner})

    def start(self) -> None:
        self.trace.emit("AudioService", "AudioFlinger", "START_OUTPUT")
        self.flinger.start_output()

    def pause(self) -> None:
        self.trace.emit("AudioService", "AudioFlinger", "PAUSE_OUTPUT")
        self.flinger.pause_output()

    def write(self) -> None:
        self.flinger.write_audio()

    def resume(self) -> None:
        self.trace.emit("AudioService", "AudioFlinger", "RESUME_OUTPUT")
        self.flinger.resume_output()
        self.write()

    def set_volume(self, value: float) -> None:
        self.trace.emit("AudioService", "AudioFlinger", "SET_VOLUME", {"volume": value})
        self.flinger.hal.set_volume(value)


class MediaService:
    def __init__(self, trace: TraceLogger, audio: AudioService):
        self.trace = trace
        self.audio = audio
        self.state = "IDLE"
        self.current_track = ""

    def handle_command(self, command: str, payload: Optional[Dict[str, Any]] = None) -> None:
        payload = payload or {}
        self.trace.emit("MediaService", "MediaService", "COMMAND_RECEIVED", {"command": command, **payload})
        if command == "PLAY":
            self.current_track = payload.get("track", "Unknown Track")
            self.audio.request_focus("MediaService")
            self.audio.start()
            self.audio.write()
            self.state = "PLAYING"
            self.trace.emit("MediaService", "IVI_HMI", "STATE_UPDATE", {"state": self.state, "track": self.current_track})
        elif command == "PAUSE":
            self.audio.pause()
            self.state = "PAUSED"
            self.trace.emit("MediaService", "IVI_HMI", "STATE_UPDATE", {"state": self.state})
        elif command == "RESUME":
            self.audio.request_focus("MediaService")
            self.audio.resume()
            self.state = "PLAYING"
            self.trace.emit("MediaService", "IVI_HMI", "STATE_UPDATE", {"state": self.state})
        elif command == "NEXT":
            self.current_track = payload.get("track", "Next Track")
            if self.state == "PLAYING":
                self.audio.write()
            self.trace.emit("MediaService", "IVI_HMI", "STATE_UPDATE", {"state": self.state, "track": self.current_track})
        elif command == "VOLUME":
            value = float(payload.get("value", 0.70))
            self.audio.set_volume(value)
        elif command == "STOP":
            self.audio.pause()
            self.audio.release_focus("MediaService")
            self.state = "IDLE"
            self.trace.emit("MediaService", "IVI_HMI", "STATE_UPDATE", {"state": self.state})
        elif command == "DUCK":
            self.audio.set_volume(float(payload.get("value", 0.30)))
            self.trace.emit("MediaService", "IVI_HMI", "AUDIO_DUCKED", {"value": payload.get("value", 0.30)})
        else:
            raise ValueError(f"Unsupported command: {command}")


class IVISimulator:
    def __init__(self):
        self.trace = TraceLogger()
        hal = AudioHAL(self.trace)
        flinger = AudioFlinger(self.trace, hal)
        audio = AudioService(self.trace, flinger)
        self.media = MediaService(self.trace, audio)

    def user_input(self, command: str, **payload: Any) -> None:
        self.trace.emit("IVI_HMI", "MediaService", "USER_INPUT", {"command": command, **payload})
        self.media.handle_command(command, payload)

    def scenario_normal_playback(self) -> None:
        self.user_input("PLAY", track="Highway Drive")
        self.user_input("VOLUME", value=0.75)
        self.user_input("NEXT", track="Night Cruise")
        self.user_input("PAUSE")
        self.user_input("RESUME")
        self.user_input("STOP")

    def scenario_navigation_ducking(self) -> None:
        self.user_input("PLAY", track="Road Focus")
        self.user_input("DUCK", value=0.30)
        self.trace.emit("NavigationService", "MediaService", "NAVIGATION_PROMPT", {"prompt": "Turn left in 300 m"})
        self.user_input("VOLUME", value=0.70)
        self.user_input("STOP")

    def scenario_call_interruption(self) -> None:
        self.user_input("PLAY", track="Connected Drive")
        self.trace.emit("TelephonyService", "AudioService", "AUDIO_FOCUS_LOSS", {"reason": "incoming_call"})
        self.user_input("PAUSE")
        self.trace.emit("TelephonyService", "AudioService", "CALL_ENDED")
        self.user_input("RESUME")
        self.user_input("STOP")

    def run(self, scenario: str) -> None:
        scenarios: Dict[str, Callable[[], None]] = {
            "normal": self.scenario_normal_playback,
            "navigation": self.scenario_navigation_ducking,
            "call": self.scenario_call_interruption,
        }
        if scenario not in scenarios:
            raise ValueError(f"Unknown scenario {scenario}. Choose from: {', '.join(scenarios)}")
        scenarios[scenario]()

    def save_outputs(self, out_dir: str | Path) -> Dict[str, str]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        log_path = out / "session_logcat.txt"
        trace_path = out / "message_trace.csv"
        summary_path = out / "summary.json"
        log_path.write_text("\n".join(self.trace.logs) + "\n", encoding="utf-8")
        with trace_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["seq", "timestamp", "source", "destination", "event", "payload"])
            for m in self.trace.messages:
                w.writerow([m.seq, m.timestamp, m.source, m.destination, m.event, json.dumps(m.payload, sort_keys=True)])
        summary = {
            "message_count": len(self.trace.messages),
            "components": sorted(set([m.source for m in self.trace.messages] + [m.destination for m in self.trace.messages])),
            "event_count": len(set(m.event for m in self.trace.messages)),
            "hal_commands": sum(1 for m in self.trace.messages if m.source == "AudioHAL"),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return {"log": str(log_path), "trace": str(trace_path), "summary": str(summary_path)}
