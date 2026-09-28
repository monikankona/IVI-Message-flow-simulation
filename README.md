# Module 6 - IVI Media Service to Audio HAL Message Flow Simulator

## Scope
This project addresses Module 6 (IVI In-Vehicle Infotainment Systems), option 3: simulate message flow between Media Service and Audio HAL and demonstrate how user input propagates through the stack.

## What is implemented
- IVI HMI user input events
- Media Service command handling
- simplified AudioService / AudioFlinger routing
- Audio HAL operations
- Android-style logcat output
- structured CSV message trace
- JSON run summary
- three scenarios: normal playback, navigation ducking, incoming-call interruption

## Architecture
IVI HMI -> Media Service -> Audio Service -> AudioFlinger -> Audio HAL -> DSP/Amplifier -> Speakers

## Requirements
- Python 3.10+
- No third-party runtime dependencies

## Run
From the project folder:

```bash
python run.py --scenario normal --output output
python run.py --scenario navigation --output output
python run.py --scenario call --output output
```

The simulator creates:
- `output/session_logcat.txt`
- `output/message_trace.csv`
- `output/summary.json`

## Notes
This is a software simulation, not a replacement for a real Android Automotive build. It models the control/message path required by the assignment so that the flow can be inspected without Android hardware.
