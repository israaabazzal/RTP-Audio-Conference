import socket
import sys
import time
import random
import audioop
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from math import gcd
from rtp import RTPPacket

RATE = 8000
FRAME = 160            # 20 ms at 8 kHz
PTIME = 0.020

def load_pcm(path):
    rate, data = wavfile.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)                 # stereo -> mono
    if data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128) * 256
    elif data.dtype == np.int32:
        data = data / 65536
    elif data.dtype in (np.float32, np.float64):
        data = data * 32767
    data = data.astype(np.float32)
    if rate != RATE:
        g = gcd(rate, RATE)
        data = resample_poly(data, RATE // g, rate // g)
    return np.clip(data, -32768, 32767).astype(np.int16)

def main(path, port=5004, host="127.0.0.1", loss=0.0):
    pcm = load_pcm(path)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ssrc = int.from_bytes(np.random.bytes(4), "big")
    seq, ts = 0, 0
    dropped = 0
    print(f"Sending {path} to {host}:{port}, SSRC={ssrc:#x}, loss={loss}%")

    start = time.perf_counter()
    n_frames = len(pcm) // FRAME
    for i in range(n_frames):
        frame = pcm[i * FRAME:(i + 1) * FRAME].tobytes()
        payload = audioop.lin2ulaw(frame, 2)       # 320 bytes -> 160 bytes
        pkt = RTPPacket(payload, seq=seq, timestamp=ts, ssrc=ssrc,
                        marker=1 if i == 0 else 0)
        if random.random() * 100 < loss:
            dropped += 1                            # skip sending: simulated loss
        else:
            sock.sendto(pkt.pack(), (host, port))
        seq += 1                                    # sequence still advances
        ts += FRAME
        # absolute-time scheduling: no drift
        wait = start + (i + 1) * PTIME - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
    print(f"Done: {n_frames} packets, {dropped} dropped on purpose")

if __name__ == "__main__":
    main(sys.argv[1],
         int(sys.argv[2]) if len(sys.argv) > 2 else 5004,
         sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1",
         float(sys.argv[4]) if len(sys.argv) > 4 else 0.0)