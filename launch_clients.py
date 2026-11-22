"""Start several test clients at once (for the scaling test).

    python launch_clients.py 6                 -> 6 clients talking to a mixer on this laptop
    python launch_clients.py 6 192.168.1.20    -> same, but the mixer is on another laptop

Each client plays one of the three tone files for 10 seconds, then stops.
Start the mixer first:  python mixer.py 5004 clients
"""
import subprocess
import sys
import time

n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
tones = ["tone440.wav", "tone660.wav", "tone880.wav"]

procs = []
for i in range(n):
    procs.append(subprocess.Popen(
        [sys.executable, "-W", "ignore", "client.py", host, tones[i % 3]],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    time.sleep(0.15)
print(f"Started {n} clients talking to {host}. Wait about 15 seconds...")
for p in procs:
    p.wait()
print("All clients finished. Now press Ctrl+C in the mixer window.")