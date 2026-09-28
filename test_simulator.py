import json
import tempfile
import unittest
from pathlib import Path

from src.ivi_simulator.core import IVISimulator


class TestIVISimulator(unittest.TestCase):
    def test_normal_playback_generates_hal_commands(self):
        sim = IVISimulator()
        sim.run("normal")
        self.assertGreater(len(sim.trace.messages), 0)
        self.assertTrue(any(m.event == "HAL_OPEN" for m in sim.trace.messages))
        self.assertTrue(any(m.event == "HAL_WRITE" for m in sim.trace.messages))
        self.assertTrue(any(m.event == "AUDIO_FOCUS_GRANTED" for m in sim.trace.messages))

    def test_call_interruption_contains_focus_loss_and_resume(self):
        sim = IVISimulator()
        sim.run("call")
        events = [m.event for m in sim.trace.messages]
        self.assertIn("AUDIO_FOCUS_LOSS", events)
        self.assertIn("CALL_ENDED", events)
        self.assertIn("RESUME_OUTPUT", events)

    def test_outputs_are_valid(self):
        sim = IVISimulator()
        sim.run("navigation")
        with tempfile.TemporaryDirectory() as td:
            paths = sim.save_outputs(td)
            self.assertTrue(Path(paths["log"]).exists())
            self.assertTrue(Path(paths["trace"]).exists())
            summary = json.loads(Path(paths["summary"]).read_text())
            self.assertEqual(summary["message_count"], len(sim.trace.messages))


if __name__ == "__main__":
    unittest.main()
