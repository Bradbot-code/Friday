import sounddevice as sd
import numpy as np

sample_rate = 44100
duration = 1
frequency = 440

times = np.linspace(
    0,
    duration,
    int(sample_rate * duration),
    endpoint=False,
)

tone = (
    0.2
    * np.sin(2 * np.pi * frequency * times)
).astype(np.float32)

print(sd.query_devices())
print("Default devices:", sd.default.device)

sd.play(tone, sample_rate)
sd.wait()