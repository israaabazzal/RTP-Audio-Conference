import sys
import numpy as np
from scipy.io import wavfile

RATE = 8000

def tone(freq, seconds=10):
    t = np.arange(int(RATE * seconds)) / RATE
    return (0.4 * 32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)

if __name__ == "__main__":
    # python make_wav.py tone440.wav 440
    name, freq = sys.argv[1], float(sys.argv[2])
    wavfile.write(name, RATE, tone(freq))
    print("wrote", name)