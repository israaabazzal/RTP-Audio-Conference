import sys
import numpy as np
import sounddevice as sd
from scipy.io import wavfile

name = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 10

print(f"Recording {secs} seconds... speak now")
rec = sd.rec(int(secs * 8000), samplerate=8000, channels=1, dtype="int16")
sd.wait()

# normalize so the loudest point is at 50% of the maximum
peak = np.abs(rec).max()
if peak > 0:
    rec = (rec.astype(np.float32) * (0.5 * 32767 / peak)).astype(np.int16)

wavfile.write(name, 8000, rec)
print("saved", name)