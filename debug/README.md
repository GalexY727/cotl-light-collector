# Regression fixtures

The supplied checkout had no debug directory. The six top-level screenshots and all ten historical cached frames were copied here without modifying their pixels. `manifest.json` records provenance and reviewed expectations. Existing green/magenta circles are old debug output, not ground truth.

Run `python main.py --test --visualize` from the repository root. Output goes under `output/`, preserving subdirectories. It is excluded from subsequent test discovery and Git.

## Manifest format

The `images` object is keyed by a relative image path. Each entry declares `state` (`friend_page`, `index`, `friend_selected`, `entry`, or `unknown`). A reviewed page can provide a complete `targets` array:

```json
{
  "version": 1,
  "images": {
    "example.png": {
      "state": "friend_page",
      "provenance": "Who inspected this image and what was visible",
      "tolerance": 0.012,
      "targets": [
        {
          "name": "Manually read friend name",
          "center": [550, 210],
          "needs_light": true,
          "collectible": true
        }
      ]
    }
  }
}
```

An optional `page_token: [total_dots, selected_zero_based_index]` validates pagination. All six reviewed originals include this field. Coordinates are pixels in the original image. Match tolerance is a fraction of its shorter dimension. Target matching is one-to-one: missing, duplicate and unexpected stars fail. A declared boolean state must match the detector. Omit a state field if it has not been reviewed; do not invent it. `targets: []` explicitly expects no targets. Omitting `targets` requests state-only smoke coverage.

For evidence obscured by a ring/nearby text, `"allow_abstain": ["collectible"]` permits the detector to return unknown while preserving the manually observed expected boolean. This is not a correct classification: the console and JSON retain the ambiguity, and live execution will not act on that target. Current allowances are Rei in image1 and Kiwi/Polo in image3. Do not use allowances to hide false predictions: the opposite boolean still fails.

The example is schema documentation, not an additional fixture. New real index, selected-friend, post-action, empty-page and click-transition captures would close current coverage gaps. Keep sequence timestamps and actual action outcomes alongside new fixtures; do not infer successful clicks from filenames.
