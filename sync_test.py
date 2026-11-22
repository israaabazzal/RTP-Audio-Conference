"""Synchronization test for the RTP mixer.

Two fake sources each send a short 'click'. Source B starts a known time AFTER
source A (0, 100 or 250 ms). We then look at the mix that comes out of the mixer
and measure how far apart the two clicks really are.

    intended offset  = what we asked for
    measured offset  = what the mixer produced
    error            = measured - intended   (this is the synchronization accuracy)

Also checks that the mixer's RTP timestamps run at the real speed of the clock.

Start the mixer first, in single-destination mode:
    python mixer.py 5004 127.0.0.1 5006 --buffer-ms 60
Then run:
    python sync_test.py
"""
import audioop
import random
import socket
import sys
import time
import numpy as np
from rtp import RTPPacket

MIXER = ("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 5004)
LISTEN_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5006
FRAME = 160            # samples per packet (20 ms)
RATE = 8000

N = 200                # packets per source (4 seconds)
CLICK_AT = 100         # the click is in packet 100 (2.0 s after the source starts)
AMPS = [8000, 16000]   # source A click is smaller, source B click is bigger


def make_frames(amp):
    frames = []
    for i in range(N):
        pcm = np.zeros(FRAME, dtype=np.int16)
        if i == CLICK_AT:
            pcm[0:8] = amp                      # a 1 ms click
        frames.append(audioop.lin2ulaw(pcm.tobytes(), 2))
    return frames


def run_case(rx, offset_ms, jitter_ms):
    ssrcs = [random.getrandbits(32) for _ in range(2)]
    frames = [make_frames(a) for a in AMPS]
    delays = [0.0, offset_ms / 1000.0]
    tx = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(2)]
    t0 = time.perf_counter() + 0.3
    events = sorted((t0 + delays[s] + i * 0.02 + random.uniform(0, jitter_ms / 1000.0), s, i)
                    for s in range(2) for i in range(N))
    out = []                                     # (arrival time, rtp timestamp, pcm)

    def pump(until):
        while time.perf_counter() < until:
            try:
                data, _ = rx.recvfrom(2048)
                p = RTPPacket.unpack(data)
                out.append((time.perf_counter(), p.timestamp,
                            np.frombuffer(audioop.ulaw2lin(p.payload, 2), dtype=np.int16)))
            except socket.timeout:
                pass

    pump(time.perf_counter() + 0.3)              # drain leftovers from the last case
    out.clear()
    for t, s, i in events:
        pump(t)
        tx[s].sendto(RTPPacket(frames[s][i], seq=i, timestamp=i * FRAME,
                               ssrc=ssrcs[s]).pack(), MIXER)
    pump(time.perf_counter() + 0.6)              # collect the end of the mix

    # --- find the clicks in the mixed audio -------------------------------
    hits = []
    for _, ts, pcm in out:
        for j in np.nonzero(np.abs(pcm) > 4000)[0]:
            hits.append((ts + int(j), int(abs(pcm[j]))))
    hits.sort()
    groups, cur = [], []
    for pos, val in hits:
        if cur and pos - cur[-1][0] > 40:
            groups.append(cur)
            cur = []
        cur.append((pos, val))
    if cur:
        groups.append(cur)
    peaks = [(g[0][0], max(v for _, v in g)) for g in groups]

    measured = None
    if len(peaks) == 1 and peaks[0][1] > 20000:
        measured = 0.0                           # both clicks in the same place
    elif len(peaks) == 2:
        a = [p for p in peaks if p[1] < 12000]
        b = [p for p in peaks if p[1] >= 12000]
        if a and b:
            measured = (b[0][0] - a[0][0]) * 1000.0 / RATE

    # --- timestamp speed check --------------------------------------------
    drift = None
    if len(out) > 20:
        ts_elapsed = ((out[-1][1] - out[0][1]) & 0xFFFFFFFF) / RATE
        wall = out[-1][0] - out[0][0]
        drift = (ts_elapsed - wall) * 1000.0
    return measured, drift, len(out)


def main():
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", LISTEN_PORT))
    rx.settimeout(0.001)
    cases = [(0, 0), (0, 30), (100, 0), (100, 30), (250, 30)]
    print(f"Sending to mixer {MIXER[0]}:{MIXER[1]}, listening for the mix on port {LISTEN_PORT}\n")
    print(f"{'intended':>9}{'jitter':>8}{'measured':>10}{'error':>8}{'clock drift':>13}{'packets':>9}")
    print(f"{'offset ms':>9}{'ms':>8}{'ms':>10}{'ms':>8}{'ms (4 s)':>13}{'heard':>9}")
    errors = []
    for offset, jitter in cases:
        m, d, n = run_case(rx, offset, jitter)
        if m is None:
            print(f"{offset:>9}{jitter:>8}{'no click':>10}{'':>8}{'':>13}{n:>9}")
        else:
            errors.append(abs(m - offset))
            print(f"{offset:>9}{jitter:>8}{m:>10.0f}{m - offset:>8.0f}{d:>13.1f}{n:>9}")
        time.sleep(1.0)
    if errors:
        print(f"\nlargest absolute error: {max(errors):.0f} ms   average: {sum(errors)/len(errors):.0f} ms")


if __name__ == "__main__":
    main()