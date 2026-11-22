import socket
import sys
import time
import threading
import audioop
from collections import deque
import numpy as np
from rtp import RTPPacket

FRAME = 160
PTIME = 0.020
PREBUFFER = 2      # frames to collect per source before mixing (40 ms)
MAX_QUEUE = 10     # drop old frames if a source runs ahead
TIMEOUT = 1.0      # forget a source after 1 s of silence
MIXER_SSRC = 0x4D495852

sources = {}       # ssrc -> {"q": deque, "started": bool, "last": float}
lock = threading.Lock()


def receiver(sock):
    while True:
        data, addr = sock.recvfrom(2048)
        try:
            pkt = RTPPacket.unpack(data)
        except Exception:
            continue
        if len(pkt.payload) != FRAME:
            continue
        pcm = np.frombuffer(audioop.ulaw2lin(pkt.payload, 2), dtype=np.int16)
        with lock:
            s = sources.setdefault(pkt.ssrc, {"q": deque(), "started": False,
                                              "last": 0})
            s["q"].append(pcm)
            while len(s["q"]) > MAX_QUEUE:
                s["q"].popleft()
            s["last"] = time.perf_counter()


def main(listen_port=5004, dest_host="127.0.0.1", dest_port=5006):
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", listen_port))
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    threading.Thread(target=receiver, args=(rx,), daemon=True).start()
    print(f"Mixer listening on {listen_port}, sending mix to {dest_host}:{dest_port}")

    seq, ts, tick = 0, 0, 0
    start = time.perf_counter()
    try:
        while True:
            mix = np.zeros(FRAME, dtype=np.int32)
            contributors = []
            now = time.perf_counter()
            with lock:
                for ssrc in list(sources):
                    s = sources[ssrc]
                    if now - s["last"] > TIMEOUT and not s["q"]:
                        del sources[ssrc]
                        continue
                    if not s["started"] and len(s["q"]) >= PREBUFFER:
                        s["started"] = True
                    if s["started"]:
                        if s["q"]:
                            mix += s["q"].popleft()
                            contributors.append(ssrc)
                        else:
                            s["started"] = False
            if contributors:
                out = np.clip(mix, -32768, 32767).astype(np.int16).tobytes()
                payload = audioop.lin2ulaw(out, 2)
                pkt = RTPPacket(payload, seq=seq, timestamp=ts,
                                ssrc=MIXER_SSRC, csrc=contributors[:15])
                tx.sendto(pkt.pack(), (dest_host, dest_port))
                seq += 1
                if seq % 50 == 0:
                    print(f"sent={seq} sources={[hex(c) for c in contributors]}")
            ts += FRAME      # the timeline always advances
            tick += 1
            wait = start + tick * PTIME - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
    except KeyboardInterrupt:
        print("Mixer stopped")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5004,
         sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1",
         int(sys.argv[3]) if len(sys.argv) > 3 else 5006)