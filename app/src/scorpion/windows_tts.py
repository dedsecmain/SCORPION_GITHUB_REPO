"""Offline Windows Speech API fallback for Scorpion MK90.

Uses only .NET System.Speech from Windows PowerShell 5.1. The spoken text
is passed on standard input, never interpolated into executable commands,
and is not sent to OpenAI or another web service.
"""
from __future__ import annotations

import base64
import os
import subprocess
from collections.abc import Callable

# EncodedCommand requires UTF-16LE. This is a fixed script: the spoken
# text itself is delivered separately over UTF-8 stdin.
_SAPI_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.SetOutputToDefaultAudioDevice()
    $german = $speaker.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'de-*' } |
        Select-Object -First 1
    if ($null -ne $german) {
        $speaker.SelectVoice($german.VoiceInfo.Name)
    }
    $speaker.Rate = 0
    $message = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($message)) { throw 'Kein Sprachtext vorhanden.' }
    $speaker.Speak($message)
} finally {
    $speaker.Dispose()
}
"""


class WindowsSpeechError(RuntimeError):
    pass


def speak_with_windows(
    text: str,
    *,
    runner: Callable | None = None,
    timeout: float | None = None,
) -> None:
    """Speak with offline Windows SAPI; raise for missing audio device/voice."""
    if os.name != "nt":
        raise WindowsSpeechError("Offline Windows-Sprache ist nur unter Windows verfügbar.")
    message = str(text or "").strip()[:1600]
    if not message:
        raise WindowsSpeechError("Kein Sprachtext vorhanden.")
    encoded = base64.b64encode(_SAPI_SCRIPT.encode("utf-16-le")).decode("ascii")
    args = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded
    ]
    execute = runner or subprocess.run
    try:
        result = execute(
            args,
            input=message,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout or min(120.0, 18.0 + len(message) * 0.09),
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WindowsSpeechError(
            "Windows-Sprachdienst konnte nicht gestartet werden oder reagiert nicht."
        ) from exc
    if result.returncode != 0:
        # Do not echo a potentially sensitive message via stderr.
        raise WindowsSpeechError(
            "Windows-Sprachausgabe fehlgeschlagen. Prüfe Standardlautsprecher, "
            "Windows-Lautstärke und installierte Stimmen."
        )
