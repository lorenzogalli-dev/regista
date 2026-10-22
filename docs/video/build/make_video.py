"""Build the demo video (docs/video/regista-demo.mp4) and its subtitles from the clips in
docs/video/clips, the title cards in cards.html and a voice-over synthesised line by line.

    python3 docs/video/build/make_video.py --voice say      # draft voice (macOS), free
    python3 docs/video/build/make_video.py --voice azure    # Azure AI Speech (en-GB neural)

Each voice-over line is its own audio file, so subtitles and cuts follow its exact length.
Needs ffmpeg and Google Chrome (cards and overlays are recorded with web/scripts/capture.mjs);
the Azure voice uses your Azure CLI login (Entra ID token, no keys).
"""

import argparse
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[3]
BUILD = Path(__file__).resolve().parent
OUT = BUILD / "out"
CLIPS = ROOT / "docs/video/clips"
CAPTURE = ROOT / "web/scripts/capture.mjs"
CARDS = f"file://{BUILD / 'cards.html'}"
FINAL = ROOT / "docs/video/regista-demo.mp4"
SRT = ROOT / "docs/video/regista-demo.srt"

AZURE_VOICE = "en-GB-RyanNeural"
SPEECH_ENDPOINT = "https://gtf-foundry.cognitiveservices.azure.com/tts/cognitiveservices/v1"
LEAD, GAP, TAIL, XFADE = 0.5, 0.35, 0.7, 0.35
FOOT_X, FOOT_Y, FOOT_W, FOOT_H = 160, 16, 1600, 900

# id, source (card name or clip file), start in the clip, section tag (kind), lines; `fit`
# speeds the clip up (at most `max_speed`) so the whole scene fits; `min_dur` gives the footage
# room; `cut` removes stretches of the clip (seconds), such as the loading gap between two tour
# steps.
SEGMENTS: list[dict] = [
    {
        "id": "title",
        "card": "title",
        "lines": [
            "This is Regista.",
            (
                "Live match graphics and tactical analysis take a team of analysts, so most "
                "matches never get them."
            ),
            "Regista generates them live, and checks every number before it goes on air.",
        ],
    },
    {
        "id": "data",
        "clip": "03-tour-data-graphics.mp4",
        "start": 1.0,
        "cut": [(8.4, 9.35), (14.95, 16.05)],
        "tag": "Computed by code",
        "kind": "code",
        "fit": True,
        "max_speed": 1.4,
        "min_dur": 14.0,
        "lines": [
            "Some graphics need no AI at all.",
            (
                "Pass difficulty, top speed, shot speed and expected goals are computed by code, "
                "the instant they happen."
            ),
        ],
    },
    {
        "id": "ai",
        "clip": "04-tour-ai-insight-replay.mp4",
        "start": 1.0,
        "tag": "AI agents · verified",
        "kind": "ai",
        "fit": True,
        "max_speed": 1.3,
        "min_dur": 29.0,
        "lines": [
            "When the game shifts, code notices first, and a template goes on air at once.",
            (
                "Behind it, six agents on Microsoft Agent Framework and Foundry go to work, "
                "reading numbers only through metrics tools over MCP."
            ),
            "The Verifier recomputes every number before the verified card replaces the template.",
            (
                "Then the frame holds, like a TV replay, and the pitch shows why, drawn from the "
                "match data."
            ),
        ],
    },
    {
        "id": "split",
        "clip": "05-tour-split.mp4",
        "start": 1.0,
        "tag": "Every viewer",
        "kind": "ai",
        "fit": True,
        "max_speed": 1.25,
        "min_dur": 12.5,
        "lines": [
            (
                "The same facts, told for different viewers: an analyst in English, a casual fan "
                "in Italian following a favourite player."
            ),
            "The numbers and the seal never change.",
        ],
    },
    {
        "id": "control",
        "clip": "06-tour-control-room.mp4",
        "start": 1.0,
        "tag": "Control room",
        "kind": "ai",
        "fit": True,
        "max_speed": 1.3,
        "min_dur": 15.0,
        "lines": [
            "In the control room, you watch the agents check each other.",
            (
                "Here the Analyst credited two players who had already been substituted. The "
                "Verifier rejected it, and only the corrected version went on air."
            ),
        ],
    },
    {
        "id": "results",
        "clip": "10-eval-report.mp4",
        "start": 0.5,
        "tag": "Measured once, on unseen matches",
        "kind": "code",
        "fit": True,
        "max_speed": 1.2,
        "min_dur": 15.5,
        "lines": [
            "We measured it on twenty unseen matches with hidden storylines the AI never sees.",
            (
                "It found about half of them, and put no explanation on air with a number the "
                "data does not support."
            ),
            "Precision is forty-three percent: the report shows where it goes wrong.",
        ],
    },
    {
        "id": "stack",
        "card": "stack",
        "lines": [
            (
                "It runs on Azure Container Apps, Microsoft Foundry, PostgreSQL, Blob Storage and"
                " Application Insights; the voice is Azure AI Speech."
            ),
        ],
    },
    {
        "id": "close",
        "card": "close",
        "min_dur": 6.5,
        "lines": [
            "Regista. Reads the game, directs the broadcast.",
        ],
    },
]

# Subtitle text where the spoken form differs from what reads best on screen.
SUBTITLE = {
    "We measured it on twenty unseen matches with hidden storylines the AI never sees.": (
        "We measured it on 20 unseen matches with hidden storylines the AI never sees."
    ),
    "Precision is forty-three percent: the report shows where it goes wrong.": (
        "Precision is 43 %: the report shows where it goes wrong."
    ),
}


def run(*cmd: str | Path) -> str:
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True).stdout


def duration(p: Path) -> float:
    return float(
        run("ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", p)
    )


def to_wav(src: Path, dst: Path) -> None:
    run("ffmpeg", "-v", "quiet", "-y", "-i", src, "-ar", "24000", "-ac", "1", dst)


def voice_say(text: str, dst: Path) -> None:
    aiff = dst.with_suffix(".aiff")
    run("say", "-v", "Daniel", "-r", "175", "-o", aiff, text)
    to_wav(aiff, dst)
    aiff.unlink()


def voice_azure(text: str, dst: Path, token: str) -> None:
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-GB">'
        f'<voice name="{AZURE_VOICE}"><prosody rate="+0%">{escape(text)}</prosody></voice></speak>'
    )
    req = urllib.request.Request(
        SPEECH_ENDPOINT,
        data=ssml.encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "regista-demo-video",
        },
    )
    raw = dst.with_suffix(".raw.wav")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw.write_bytes(r.read())
    # The service pads each line with silence; trim both ends so timings follow the speech.
    trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    run("ffmpeg", "-v", "quiet", "-y", "-i", raw, "-af", f"{trim},areverse,{trim},areverse", dst)
    raw.unlink()


def synthesise(provider: str) -> dict[str, list[tuple[str, Path, float]]]:
    vdir = OUT / f"voice-{provider}"
    vdir.mkdir(parents=True, exist_ok=True)
    token = ""
    if provider == "azure":
        token = run(
            "az",
            "account",
            "get-access-token",
            "--resource",
            "https://cognitiveservices.azure.com",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ).strip()
    chars = 0
    out: dict[str, list[tuple[str, Path, float]]] = {}
    for seg in SEGMENTS:
        out[seg["id"]] = []
        for i, line in enumerate(seg["lines"]):
            dst = vdir / f"{seg['id']}-{i}.wav"
            done = dst.with_suffix(".txt")
            if not (dst.exists() and done.exists() and done.read_text() == line):  # cache by text
                if provider == "azure":
                    voice_azure(line, dst, token)
                    chars += len(line)
                else:
                    voice_say(line, dst)
                done.write_text(line)
            out[seg["id"]].append((line, dst, duration(dst)))
    if provider == "azure":
        print(f"Azure AI Speech: {chars} characters synthesised in this run")
    return out


def overlay_png(name: str, query: dict[str, str]) -> Path:
    """A transparent 1920x1080 PNG from cards.html (subtitle, section tag)."""
    dst = OUT / "overlays" / f"{name}.png"
    key = dst.with_suffix(".txt")
    q = urllib.parse.urlencode(query)
    if not (dst.exists() and key.exists() and key.read_text() == q):
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["node", CAPTURE, "shot", f"{CARDS}?{q}", dst, "1920", "1080", "700"],
            check=True,
            capture_output=True,
            env={**__import__("os").environ, "TRANSPARENT": "1"},
        )
        key.write_text(q)
    return dst


def record_card(card: str, seconds: float) -> Path:
    dst = OUT / "cards" / f"{card}.mp4"
    key = dst.with_suffix(".txt")
    if not (dst.exists() and key.exists() and key.read_text() == f"{seconds:.2f}"):
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "node",
                CAPTURE,
                "video",
                f"{CARDS}?card={card}",
                dst,
                f"{seconds + 0.5:.2f}",
                "1920",
                "1080",
            ],
            check=True,
            capture_output=True,
            env={**__import__("os").environ, "SETTLE_MS": "400"},
        )
        key.write_text(f"{seconds:.2f}")
    return dst


def build_segment(
    seg: dict, lines: list[tuple[str, Path, float]], frame: Path
) -> tuple[Path, float, list]:
    """Render one segment (video only); returns its file, duration and line timings (local)."""
    speech = sum(d for _, _, d in lines) + GAP * (len(lines) - 1)
    dur = max(LEAD + speech + TAIL, seg.get("min_dur", 0.0))
    timings, t = [], LEAD
    for text, wav, d in lines:
        timings.append((t, t + d, text, wav))
        t += d + GAP

    inputs: list[str | Path] = []
    filters: list[str] = []
    if "card" in seg:
        inputs += ["-i", record_card(seg["card"], dur)]
        filters.append(f"[0:v]trim=0:{dur:.3f},setpts=PTS-STARTPTS,fps=30[base]")
    else:
        clip = CLIPS / seg["clip"]
        cuts = seg.get("cut", [])
        avail = duration(clip) - seg["start"] - sum(b - a for a, b in cuts)
        keep = f"gte(t,{seg['start']})" + "".join(f"*not(between(t,{a},{b}))" for a, b in cuts)
        speed = min(seg.get("max_speed", 1.0), max(1.0, avail / dur)) if seg.get("fit") else 1.0
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", frame, "-i", clip]
        filters.append(
            f"[1:v]fps=30,select='{keep}',setpts=N/(30*TB)/{speed:.4f},fps=30,"
            f"scale={FOOT_W}:{FOOT_H}:force_original_aspect_ratio=decrease,"
            f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=0:{dur:.3f},setpts=PTS-STARTPTS[clip]"
        )
        filters.append(f"[0:v][clip]overlay=x=(W-w)/2:y={FOOT_Y},fps=30[base]")
        print(f"  {seg['id']}: {dur:.1f} s, clip x{speed:.2f} ({avail:.1f} s available)")
    last = "base"
    n = 2 if "card" not in seg else 1
    if seg.get("tag"):
        png = overlay_png(f"tag-{seg['id']}", {"tag": seg["tag"], "kind": seg.get("kind", "code")})
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", png]
        filters.append(f"[{n}:v]format=rgba,fade=in:st=0.3:d=0.3:alpha=1[tag]")
        filters.append(f"[{last}][tag]overlay=0:0[v{n}]")
        last, n = f"v{n}", n + 1
    for i, (a, b, text, _) in enumerate(timings):
        png = overlay_png(f"sub-{seg['id']}-{i}", {"sub": SUBTITLE.get(text, text)})
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", png]
        filters.append(
            f"[{n}:v]format=rgba,fade=in:st={max(0, a - 0.1):.3f}:d=0.12:alpha=1,"
            f"fade=out:st={b + 0.15:.3f}:d=0.12:alpha=1[s{n}]"
        )
        filters.append(
            f"[{last}][s{n}]overlay=0:0:"
            f"enable='between(t,{max(0, a - 0.1):.3f},{b + 0.27:.3f})'[v{n}]"
        )
        last, n = f"v{n}", n + 1
    dst = OUT / "segments" / f"{seg['id']}.mp4"
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(
        "ffmpeg",
        "-v",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{last}]",
        "-t",
        f"{dur:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "16",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        dst,
    )
    return dst, dur, timings


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", choices=["say", "azure"], default="say")
    a = ap.parse_args()
    voice = synthesise(a.voice)
    frame = OUT / "frame.png"
    if not frame.exists():
        frame.parent.mkdir(parents=True, exist_ok=True)
        run("node", CAPTURE, "shot", f"{CARDS}?frame=1", frame, "1920", "1080", "500")

    built = [build_segment(s, voice[s["id"]], frame) for s in SEGMENTS]

    # Video: segments joined by short cross-fades; every segment starts XFADE earlier than the
    # end of the previous one.
    starts, t = [], 0.0
    for i, (_, d, _) in enumerate(built):
        starts.append(t)
        t += d - (XFADE if i < len(built) - 1 else 0)
    total = t
    inputs: list[str | Path] = []
    for f, _, _ in built:
        inputs += ["-i", f]
    chain, last, acc = [], "0:v", built[0][1]
    for i in range(1, len(built)):
        out = f"x{i}"
        chain.append(
            f"[{last}][{i}:v]xfade=transition=fade:duration={XFADE}:offset={acc - XFADE:.3f}[{out}]"
        )
        last, acc = out, acc + built[i][1] - XFADE

    # Audio: every line at its absolute time, then loudness-normalised.
    lines = [
        (starts[k] + a, starts[k] + b, text, wav)
        for k, (_, _, tl) in enumerate(built)
        for a, b, text, wav in tl
    ]
    n0 = len(built)
    for _, _, _, wav in lines:
        inputs += ["-i", wav]
    for j, (a, _, _, _) in enumerate(lines):
        chain.append(f"[{n0 + j}:a]adelay={round(a * 1000)}:all=1[a{j}]")
    chain.append(
        "".join(f"[a{j}]" for j in range(len(lines)))
        + f"amix=inputs={len(lines)}:normalize=0:duration=longest,apad,atrim=0:{total:.3f},"
        "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
    )
    chain.append(
        f"[{last}]scale=out_range=tv,format=yuv420p[vout]"
    )  # screencast frames are full range
    run(
        "ffmpeg",
        "-v",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(chain),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-profile:v",
        "high",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ac",
        "2",
        "-color_range",
        "tv",
        "-movflags",
        "+faststart",
        "-t",
        f"{total:.3f}",
        FINAL,
    )

    SRT.write_text(
        "\n".join(
            f"{i}\n{srt_time(a)} --> {srt_time(b + 0.25)}\n{SUBTITLE.get(text, text)}\n"
            for i, (a, b, text, _) in enumerate(lines, 1)
        )
    )
    (OUT / "timeline.json").write_text(
        json.dumps(
            {
                "total_s": total,
                "segments": [
                    {"id": s["id"], "start": st, "dur": d}
                    for s, st, (_, d, _) in zip(SEGMENTS, starts, built, strict=True)
                ],
                "lines": [{"start": a, "end": b, "text": text} for a, b, text, _ in lines],
            },
            indent=2,
        )
    )
    print(
        f"{FINAL.relative_to(ROOT)}: {duration(FINAL):.2f} s; "
        f"{SRT.relative_to(ROOT)}: {len(lines)} subtitles"
    )


if __name__ == "__main__":
    main()
