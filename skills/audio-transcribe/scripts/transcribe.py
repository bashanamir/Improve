#!/usr/bin/env python3
"""
Generic audio/video transcription using OpenAI's Whisper API.

Takes ANY audio or video file, splits it into chunks if it exceeds the
API's ~25MB per-request limit, transcribes each chunk with Whisper, and
stitches the result back into a single transcript.

Usage:
    python transcribe.py INPUT_FILE [--output OUTPUT_FILE] [--language he]
                         [--model whisper-1] [--format text]

Requires:
    pip install openai pydub python-dotenv
    ffmpeg installed on the system (pydub shells out to it for splitting
    and format conversion — on Debian/Ubuntu: apt-get install ffmpeg)

Environment:
    OPENAI_API_KEY must be set (in the environment or a .env file next to
    this script / in the current working directory).
"""
import argparse
import os
import sys
import time

# 25MB is OpenAI's hard limit per request. We stay a bit under it to leave
# room for container/format overhead after re-encoding a chunk.
MAX_CHUNK_BYTES = 24 * 1024 * 1024
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

# Formats Whisper accepts natively. Anything else gets converted by pydub
# during the chunking step (pydub/ffmpeg reads almost anything as input).
SUPPORTED_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"}


def get_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "OPENAI_API_KEY not found. Set it as an environment variable, "
            "or put it in a .env file (OPENAI_API_KEY=sk-...) in the "
            "current directory."
        )
    return OpenAI(api_key=api_key)


def needs_chunking(file_path):
    return os.path.getsize(file_path) > MAX_CHUNK_BYTES


def split_into_chunks(file_path, work_dir):
    """
    Splits an audio/video file into time-based chunks that each stay under
    MAX_CHUNK_BYTES, by first measuring the file's bytes-per-second and
    picking a chunk duration accordingly. Exports each chunk as mp3 (small,
    universally supported by the API) using pydub (needs ffmpeg installed).

    Returns a list of chunk file paths, in order.
    """
    from pydub import AudioSegment

    print(f"Loading {file_path} for chunking (this can take a moment for video files)...")
    audio = AudioSegment.from_file(file_path)

    total_ms = len(audio)
    total_bytes = os.path.getsize(file_path)
    bytes_per_ms = total_bytes / max(total_ms, 1)

    # Target a bit under the max to leave margin, and never go below 30s
    # chunks (avoids absurd numbers of API calls for weird bitrates).
    target_bytes = MAX_CHUNK_BYTES * 0.9
    chunk_ms = max(int(target_bytes / bytes_per_ms), 30_000)

    os.makedirs(work_dir, exist_ok=True)
    chunk_paths = []
    for i, start_ms in enumerate(range(0, total_ms, chunk_ms)):
        chunk = audio[start_ms : start_ms + chunk_ms]
        chunk_path = os.path.join(work_dir, f"chunk_{i:03d}.mp3")
        chunk.export(chunk_path, format="mp3")
        chunk_paths.append(chunk_path)
        print(f"  chunk {i}: {start_ms/1000:.0f}s-{min(start_ms+chunk_ms, total_ms)/1000:.0f}s "
              f"({os.path.getsize(chunk_path)/1_000_000:.1f}MB)")

    return chunk_paths


def transcribe_one(client, file_path, model, language, response_format):
    """Transcribes a single file (or chunk), with retries on transient errors."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(file_path, "rb") as f:
                kwargs = {"model": model, "file": f, "response_format": response_format}
                if language:
                    kwargs["language"] = language
                result = client.audio.transcriptions.create(**kwargs)
            # response_format="text" returns a plain string; other formats
            # (json/verbose_json) return an object with a .text attribute.
            return result if isinstance(result, str) else result.text
        except Exception as e:
            last_error = e
            print(f"  attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"Transcription failed after {MAX_RETRIES} attempts: {last_error}")


def transcribe_file(input_path, model="whisper-1", language=None, response_format="text",
                     keep_chunks=False):
    """
    Main entry point. Returns the full transcript as a string.
    Handles chunking transparently if the file is too large for one request.
    """
    if not os.path.exists(input_path):
        sys.exit(f"File not found: {input_path}")

    client = get_client()

    if not needs_chunking(input_path):
        print(f"Transcribing {input_path} in a single request...")
        return transcribe_one(client, input_path, model, language, response_format)

    print(f"{input_path} is over the size limit — splitting into chunks first...")
    work_dir = input_path + "_chunks"
    chunk_paths = split_into_chunks(input_path, work_dir)

    transcripts = []
    try:
        for i, chunk_path in enumerate(chunk_paths):
            print(f"Transcribing chunk {i+1}/{len(chunk_paths)}...")
            text = transcribe_one(client, chunk_path, model, language, response_format)
            transcripts.append(text)
    finally:
        if not keep_chunks:
            for chunk_path in chunk_paths:
                os.remove(chunk_path)
            if os.path.isdir(work_dir) and not os.listdir(work_dir):
                os.rmdir(work_dir)

    return "\n\n".join(transcripts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Path to any audio or video file")
    parser.add_argument("--output", "-o", help="Where to save the transcript (default: <input>.transcript.txt)")
    parser.add_argument("--language", "-l", default=None,
                         help="ISO-639-1 language hint (e.g. 'he', 'en'). Improves accuracy; omit for auto-detect.")
    parser.add_argument("--model", default="whisper-1", help="Transcription model (default: whisper-1)")
    parser.add_argument("--format", default="text", choices=["text", "srt", "vtt", "json", "verbose_json"],
                         help="Output format from the API (default: text)")
    parser.add_argument("--keep-chunks", action="store_true",
                         help="Don't delete intermediate audio chunks after transcribing")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    transcript = transcribe_file(
        args.input, model=args.model, language=args.language,
        response_format=args.format, keep_chunks=args.keep_chunks,
    )

    output_path = args.output or (args.input + ".transcript.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"\nDone. Transcript saved to: {output_path}")


if __name__ == "__main__":
    main()
