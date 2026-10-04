import numpy as np
from assistant.audio_filter import SpeechGate


def test_silence_and_tones_do_not_open_gate():
    for frequency in (0,440,1000):
        gate=SpeechGate()
        t=np.arange(3200)/16000
        samples=(.1*np.sin(2*np.pi*frequency*t)).astype(np.float32)
        for _ in range(20):
            assert not np.any(gate.filter(samples))
        assert not gate.supports_line(0,4)


def test_isolated_click_does_not_open_gate_or_mutate_input():
    gate=SpeechGate();samples=np.zeros(3200,dtype=np.float32);samples[100]=.8
    original=samples.copy()
    assert not np.any(gate.filter(samples))
    assert np.array_equal(original,samples)
    assert not gate.supports_line(0,.2)
