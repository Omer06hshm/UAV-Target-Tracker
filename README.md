# UAV Target Tracker

Real-time red/blue ground-target detection and lock tracking for the TEKNOFEST fixed-wing UAV project.

## Current goals
- Detect red and blue square targets with OpenCV/HSV
- Keep independent RED and BLUE locks
- Prevent target jumping once a lock is valid
- Reacquire safely after temporary loss
- Resize the tracking box as apparent target size changes
- Maintain smooth real-time performance on the OBS Virtual Camera feed

## Current test setup
- Python + OpenCV
- Windows
- OBS Virtual Camera: camera index **2**
- Processing resolution: **640x360**
- Target runtime: **25-30 FPS or better**

## Run
```powershell
.\.venv\Scripts\python.exe target_detector_live.py
```

Press **Q** or **Esc** to quit. Press **M** to toggle masks.

## Development workflow
Tony (ChatGPT) owns architecture/review through GitHub. Cursor may implement and test changes locally, then push them back through branches/PRs.

See `CURSOR.md` before changing the tracker.
