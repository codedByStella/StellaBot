"""Persistent Windows SAPI voice worker."""

import base64
import re
import subprocess
import threading

from companion_app.logging import wlog, wlog_exc

_kokoro_worker_lock = threading.Lock()
_kokoro_worker = None


def _kokoro_worker_script():
    """Return the PowerShell script for the persistent Kokoro worker."""
    return r"""
    $ErrorActionPreference = "Stop"
    Add-Type -AssemblyName System.Speech

    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer

    try {
        $s.SelectVoice("Kokoro Heart (en-US)")
    }
    catch {
        [Console]::Out.WriteLine("ERROR: Required SAPI voice 'Kokoro Heart (en-US)' is not installed.")
        $s.Dispose()
        exit 2
    }

    $s.Rate = 0
    $s.Volume = 100

    [Console]::Out.WriteLine("__KOKORO_READY__")
    [Console]::Out.Flush()

    try {
        while ($true) {
            $line = [Console]::In.ReadLine()

            if ($null -eq $line) { break }
            if ($line -eq "__KOKORO_QUIT__") { break }
            if ($line.Length -eq 0) { continue }

            try {
                $bytes = [Convert]::FromBase64String($line)
                $inputText = [Text.Encoding]::UTF8.GetString($bytes)

                if ($inputText.Length -gt 0) {
                    # Normalize whitespace before synthesis.
                    $inputText = [regex]::Replace(
                        $inputText,
                        '[\r\n]+',
                        ' '
                    )

                    $inputText = [regex]::Replace(
                        $inputText,
                        '\s+',
                        ' '
                    ).Trim()

                    # Kokoro's native comma pause is short and reliable.
                    # Extend sentence breaks without introducing SSML.
                    $inputText = [regex]::Replace(
                        $inputText,
                        '[.!?]',
                        ',,,'
                    )

                    $s.Speak($inputText)
                }
            }
            catch {
                Write-Error $_
            }
        }
    }
    finally {
        $s.Dispose()
    }
    """


def _start_kokoro_worker():
    """Start the persistent Kokoro Heart SAPI worker."""
    global _kokoro_worker

    ps_script = _kokoro_worker_script()

    _kokoro_worker = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_script,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    ready = _kokoro_worker.stdout.readline().strip()

    if ready != "__KOKORO_READY__":
        detail = ready or (
            f"worker exited with code {_kokoro_worker.poll()}"
        )

        try:
            _kokoro_worker.kill()
        except Exception:
            pass

        _kokoro_worker = None

        raise RuntimeError(
            "Kokoro SAPI worker failed to initialize: "
            + detail
        )


def _speak_kokoro(text):
    """Speak through one persistent Kokoro Heart SAPI worker."""
    global _kokoro_worker

    clean = str(text).strip()

    if not clean:
        return

    # Prevent long pauses caused by line breaks and excess whitespace.
    clean = re.sub(r"[\r\n]+", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    if not clean:
        return

    with _kokoro_worker_lock:
        if (
            _kokoro_worker is None
            or _kokoro_worker.poll() is not None
        ):
            wlog(
                "VOICE",
                "starting persistent Kokoro Heart worker",
            )

            _start_kokoro_worker()

            wlog(
                "VOICE",
                "persistent Kokoro Heart worker ready",
            )

        payload = base64.b64encode(
            clean.encode("utf-8")
        ).decode("ascii")

        try:
            _kokoro_worker.stdin.write(payload + "\n")
            _kokoro_worker.stdin.flush()

            wlog(
                "VOICE",
                (
                    f"queued {len(clean)} chars "
                    "to persistent Kokoro worker"
                ),
            )

        except (BrokenPipeError, OSError):
            wlog(
                "VOICE",
                "persistent Kokoro worker died; restarting once",
            )

            try:
                _kokoro_worker.kill()
            except Exception:
                pass

            _kokoro_worker = None

            _start_kokoro_worker()

            _kokoro_worker.stdin.write(payload + "\n")
            _kokoro_worker.stdin.flush()

            wlog(
                "VOICE",
                (
                    f"queued {len(clean)} chars "
                    "after worker restart"
                ),
            )


def speak(text):
    wlog(
        "VOICE",
        f"speak() start | {len(str(text or ''))} chars",
    )

    try:
        raw = str(text).strip()

        if not raw:
            wlog(
                "VOICE",
                "speak() returned: empty raw text",
            )
            return

        clean = re.sub(
            r"\*([^*]+)\*",
            r"\1",
            raw,
        )

        clean = clean.replace("*", "").strip()

        if not clean:
            wlog(
                "VOICE",
                "speak() returned: empty cleaned text",
            )
            return

        wlog(
            "VOICE",
            f"speaking with Kokoro Heart | {len(clean)} chars",
        )

        _speak_kokoro(clean)

        wlog(
            "VOICE",
            "Kokoro Heart playback queued",
        )

    except Exception as exc:
        wlog(
            "VOICE",
            (
                "UNHANDLED speak() ERROR: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

        print(
            f"[VOICE] UNHANDLED speak() ERROR: "
            f"{type(exc).__name__}: {exc}"
        )


# ============================================================

def shutdown_voice_worker():
    """Stop the persistent SAPI worker, escalating only if it will not exit."""
    global _kokoro_worker

    try:
        with _kokoro_worker_lock:
            worker = _kokoro_worker
            _kokoro_worker = None

            if worker is not None and worker.poll() is None:
                try:
                    if worker.stdin and not worker.stdin.closed:
                        worker.stdin.write("__KOKORO_QUIT__\n")
                        worker.stdin.flush()
                        worker.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

                try:
                    worker.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    worker.terminate()

                    try:
                        worker.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        worker.kill()

    except Exception as exc:
        wlog_exc("SHUTDOWN", exc)
