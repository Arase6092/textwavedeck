# WaveDeck Modes, Shortcuts, and Gestures

This document describes the current public control model in `v0.1.0`.

## First Rule

Gesture controls only work when all of the following are true:

- a PPT project is already loaded
- the app is in gesture mode
- the gesture runtime is not locked

To enter gesture mode, press `Ctrl+Alt+M`.

## Mode Guide

### PPT Preview

Use this when you want thumbnails and fast page selection.

- left rail: select a slide directly
- double-click the main slide: enter slideshow mode
- `Ctrl+Alt+M`: switch to gesture mode

### PPT Slideshow

Use this when you want a clean single-slide presentation surface.

- click: next slide
- double-click: return to preview
- `Esc`: return to preview
- `Ctrl+Alt+M`: switch to gesture mode

### Gesture Carousel

Use this when you want to browse nearby slides spatially.

- the center page is the current page
- nearby pages remain visible for context
- mouse drag / wheel: rotate the carousel
- `Ctrl+Alt+M`: return to the last PPT submode

### Gesture Stage

Use this when you want to zoom, pan, swipe, or point at one slide.

- zoom controls appear in the bottom chrome
- `Esc`: return to the carousel
- `Ctrl+Alt+M`: return to PPT mode

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O` | Open a PowerPoint file |
| `Ctrl+Alt+M` | Switch between PPT mode and gesture mode |
| `PageDown`, `Right`, `Space`, `N` | Next slide |
| `PageUp`, `Left`, `P` | Previous slide |
| `Home` | First slide |
| `End` | Last slide |
| `F11` | Enter or leave fullscreen |
| `Esc` | Leave fullscreen, or return from gesture stage to gesture carousel |

## Gesture Mapping

All gesture behavior below describes the current implementation in `gesture/controller.py`.

| Gesture | Where It Works | Result |
| --- | --- | --- |
| Hold a single fist for about `650 ms` | Gesture mode | Lock gesture control |
| Show any non-fist hand after lock | Gesture mode | Auto-unlock gesture control |
| Open palm, swipe left | Gesture carousel or gesture stage | Next slide |
| Open palm, swipe right | Gesture carousel or gesture stage | Previous slide |
| `OK` gesture held for about `90 ms` | Gesture carousel | Enter gesture stage for the current slide |
| `OK` gesture held for about `90 ms` | Gesture stage | Return to gesture carousel |
| Right-hand index finger only | Gesture stage | Pan the slide |
| Two open palms moving apart | Gesture stage | Zoom in |
| Two open palms moving closer | Gesture stage | Zoom out |
| Index + middle finger extended, ring + pinky folded | Gesture stage | Show laser pointer |

## Gesture Details

### 1. Lock / Unlock

- A single held fist pauses gesture execution.
- This is useful when you want to keep your hands visible but stop triggering commands.
- To recover, open your hand or switch to any non-fist gesture.

### 2. Swipe Navigation

- WaveDeck treats a horizontal open-palm swipe as slide navigation.
- Swiping left goes to the next slide.
- Swiping right goes to the previous slide.
- The gesture cooldown is about `450 ms`, so repeated page changes are intentionally rate-limited.

### 3. OK Gesture

The `OK` gesture is used as a mode toggle inside gesture mode:

- in the carousel: open the current slide as a single-slide stage
- in the stage: return to the carousel

This is different from `Ctrl+Alt+M`, which switches between PPT mode and gesture mode.

### 4. Pan

- Pan is available only in gesture stage.
- It currently expects a right-hand index-only pose.
- Small motion is ignored until the movement is stable enough to avoid jitter.

### 5. Zoom

- Zoom is available only in gesture stage.
- Both hands need to be open palms.
- The controller waits for a short activation window before treating the pose as zoom intent.
- After activation:
  moving hands apart zooms in
  moving hands together zooms out

### 6. Laser Pointer

- Laser pointer is available only in gesture stage.
- It uses a two-finger pointing pose:
  index finger extended
  middle finger extended
  ring finger folded
  little finger folded

The pointer is smoothed and can briefly survive short detection dropouts.

## Recommended Learning Path

If you are trying gesture mode for the first time:

1. Use `Ctrl+Alt+M` to enter gesture mode.
2. Start with open-palm left/right swipes.
3. Learn the `OK` gesture to switch between carousel and stage.
4. Try two-hand zoom only after stage mode feels stable.
5. Use fist lock whenever you need to pause gesture input.

## Troubleshooting

### Gestures do nothing

Check these in order:

1. A PPT file is already loaded
2. You are in gesture mode, not PPT preview/slideshow
3. Gesture control is not locked

### The app seems frozen after a fist

It is probably locked, not broken.

- Open your hand
- or switch to any non-fist pose

The current runtime will auto-unlock once a non-fist hand is detected.

### Zoom is hard to trigger

- Use two clear open palms
- keep both hands visible for a short moment
- then move both hands apart or together with intentional bilateral motion

### The slide moves instead of changing page

That usually means you are in gesture stage and using a pan-compatible pose.

- use an open-palm horizontal swipe for page turns
- use the `OK` gesture if you want to switch back to the carousel first

## Scope Note

This document describes the current public behavior. Gesture ergonomics are still being refined, so thresholds and recognition details may continue to improve across later releases.
