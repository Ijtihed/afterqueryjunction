# Pitch video

`crucible-pitch.mp4` is the 90 second pitch: a spoken intro, then twelve slides cut to a voiceover, with subtitles.

Every slide frame is drawn by `scripts/make_video.py`. Chamber footage is simulator frames from recorded Harbor trials, and the counts shown are exhaustive (`scripts/analyze.py`). `plan.json` holds the slide order and timings fitted to the voiceover by `scripts/voice_align.py`; `final.subs.json` holds the subtitles.

The raw intro clip and voice recording are not in this repository, so the video cannot be re-rendered from a clone without supplying your own.

Fonts in `fonts/` are Manrope and JetBrains Mono, both under the SIL Open Font License 1.1, from https://github.com/google/fonts.
