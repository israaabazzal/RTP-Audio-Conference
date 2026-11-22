import sounddevice as sd


print("Recording 3 seconds... speak now")
rec = sd.rec(int(3 * 8000), samplerate=8000, channels=1, dtype="int16")
sd.wait()

print("Playing back...")
sd.play(rec, 8000)
sd.wait()

print("Done")