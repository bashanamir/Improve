---
name: audio-transcribe
description: Transcribe any audio or video file into text using OpenAI's Whisper API. Use this whenever the user wants to transcribe a recording, lecture, meeting, podcast, interview, voice memo, or any audio/video file — not limited to any specific course or project. Handles files larger than the API's 25MB limit by automatically splitting them into chunks and stitching the transcript back together. Trigger on phrases like "transcribe this", "תמלל את זה", "get the text from this recording", or when the user provides an audio/video file and asks what's said in it.
---

# Audio Transcribe (Whisper)

A generic skill for transcribing any audio or video file with OpenAI's
Whisper API. This was extracted from a lesson-transcription pipeline, but
it has no dependency on that use case — it works on any input file.

## When to use this

Use whenever someone wants an audio or video file turned into text:
recordings of meetings, lectures, podcasts, interviews, voice memos, phone
calls, etc. This is about **transcription only** — turning audio into text.
If the user also wants the transcript summarized or turned into structured
notes afterward, do that as a separate step after transcription completes
(see "Chaining" below) — don't conflate the two.

## Prerequisites

1. An `OPENAI_API_KEY` must be available, either:
   - already set as an environment variable, or
   - in a `.env` file in the working directory (`OPENAI_API_KEY=sk-...`)

   If neither is present, ask the user for their OpenAI API key before
   proceeding — don't guess or fabricate one.

2. Python dependencies (install once per environment):
   ```bash
   pip install -r scripts/requirements.txt --break-system-packages
   ```

3. `ffmpeg` must be installed on the system (pydub shells out to it for
   splitting/re-encoding). Check with `ffmpeg -version`; if missing:
   ```bash
   apt-get update && apt-get install -y ffmpeg
   ```

## How to run it

The heavy lifting is in `scripts/transcribe.py`. Don't reimplement chunking
or retry logic inline — call this script.

```bash
python scripts/transcribe.py path/to/recording.mp4
```

This automatically:
- Detects whether the file exceeds the ~25MB per-request API limit
- If it does, splits it into time-based mp3 chunks under the limit
  (using pydub — proportional to the file's actual bitrate, not a fixed
  duration guess) and transcribes each chunk in order
- Retries transiently-failed requests up to 3 times with backoff, instead
  of failing the whole job on one network hiccup
- Concatenates all chunk transcripts into one text file
- Saves the result next to the input as `<filename>.transcript.txt`
  (or wherever `--output` points)

### Useful flags

| Flag | Purpose |
|---|---|
| `--output PATH` / `-o` | Custom output path for the transcript |
| `--language he` / `-l` | ISO-639-1 hint (e.g. `he`, `en`) — improves accuracy for known-language audio; omit to auto-detect |
| `--model whisper-1` | Override the transcription model |
| `--format srt` | Get timestamped subtitles (`srt`/`vtt`) instead of plain text (`text`, default) |
| `--keep-chunks` | Keep the intermediate audio chunks instead of deleting them after the run |

Example — Hebrew lecture recording, subtitles output:
```bash
python scripts/transcribe.py lecture.m4a --language he --format srt -o lecture.srt
```

## What "generic" means here

Nothing in this skill assumes:
- a specific source (Google Drive, local upload, a specific app export — doesn't matter, just needs a local file path)
- a specific language or subject matter
- a specific downstream use (course notes, meeting minutes, etc.)

If the user's original file lives somewhere other than local disk (a
Google Drive link, a Slack attachment, etc.), download it to a local path
first with whatever tool applies, then hand that local path to this
script — that step is intentionally outside this skill's scope.

## Chaining into a summary (optional next step)

If the user also wants insights/summary/notes extracted from the
transcript (not just the raw text), that's a second, separate step: feed
the saved `.transcript.txt` content to an LLM call with a prompt describing
the desired summary format. Keep this decoupled from transcription itself
so the skill stays reusable for transcription-only requests too.

## Cost note

Whisper API pricing is per-minute of audio (roughly $0.006/min as of this
writing — check current OpenAI pricing since this can change). A 1-hour
recording costs on the order of $0.35–0.50. Mention this to the user for
long files if it seems relevant, but don't block on it.
