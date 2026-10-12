# Cursor Instructions

You are the implementation agent for the UAV Target Tracker project.

## Source of truth
Use this GitHub repository as the source of truth. Review open issues, pull requests, README, and recent changes before modifying code.

## Project ownership
Tony (ChatGPT) owns architecture, engineering direction, and code review.
Cursor owns local implementation, execution, testing, profiling, and environment-specific fixes.

## Non-negotiable project facts
- Windows development machine
- OBS Virtual Camera is **CAMERA_INDEX = 2**
- Main live tracker file: `target_detector_live.py`
- Python + OpenCV
- Current processing target: 640x360
- Desired live performance: >=25 FPS where practical
- Q and Esc must exit cleanly

## Tracking behavior
- RED and BLUE must have independent tracker state
- Initial lock requires persistence across multiple frames
- Once locked, continuity must beat raw color score so the tracker does not jump
- Background candidates may be checked but must not steal a healthy lock
- Reacquisition should happen only after the original target is genuinely lost and a replacement is verified
- Bounding box must resize smoothly as apparent target size changes with distance
- Preserve useful diagnostics such as FPS and pixel X/Y error
- Prefer robust, readable code over clever complexity

## Workflow
1. Pull latest `main`.
2. Read any open GitHub issue assigned to the task.
3. Create a feature/fix branch.
4. Make the smallest coherent change.
5. Run the code locally.
6. Report actual FPS/errors/behavior observed.
7. Commit and push the branch.
8. Open a PR with:
   - what changed
   - why
   - how it was tested
   - observed FPS
   - any remaining issue
9. Do not merge architecture-changing work without Tony review.

Do not silently replace working behavior with a different design. If requirements conflict, raise it in the PR instead.
