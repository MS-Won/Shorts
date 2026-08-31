# Music assets

YouTube's Audio Library has no public API, so tracks must be added here by hand:

1. Go to https://studio.youtube.com → Audio Library.
2. Filter to tracks that are safe for monetized use (no attribution required, or note the
   attribution text if required).
3. Download the mp3 and place it in this folder.
4. Add an entry to `manifest.json` under a mood key matching the `audio_mood` values the
   idea generator produces (freeform strings are fine — `pick_music` falls back to any
   track if no exact mood match exists), e.g.:

   ```json
   {
     "tense and driving": [{"file": "tense_1.mp3", "attribution": ""}],
     "upbeat": [{"file": "upbeat_1.mp3", "attribution": ""}]
   }
   ```

Add at least 8-10 tracks across a few moods before the first real pipeline run, so
`pick_music` has real variety instead of reusing the same track every day.
