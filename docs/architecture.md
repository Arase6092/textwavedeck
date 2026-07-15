# WaveDeck Architecture

WaveDeck is split into a few focused layers:

## App Layer

`app/` owns the main window, theme, command wiring, and background import workflow.

## PPT Pipeline

`ppt/` validates source files, computes cache keys, runs PowerPoint COM export, and persists project metadata.

## UI Layer

`widgets/` contains the preview workspace, theatre carousel, single-slide stage, and transition overlays.

## Project Model

`models/` defines the exported slide project and page metadata shared by the pipeline and the UI.

## Gesture Runtime

`gesture/` contains the current experimental gesture pipeline. The public release keeps the slide-stage experience as the primary product surface.
