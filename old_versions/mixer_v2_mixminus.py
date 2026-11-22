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
PREBUFFER = 2          # frames to collect per source before mixing (40 ms)
MAX_QUEUE = 10         # drop old frames if a source runs ahead
TIMEOUT = 5.0          # forget a source after 5 s of silence
MIXER_SSRC = 0x4D495852

# ssrc -> state of one participant
#   q         : queued PCM frames (receiver thread appends, main loop pops)
#   started   : True once PREBUFFER frames have been collected
#   last      : time of the last packet received
#   addr      : (ip, port) this client sends from, and where its mix goes back
#   seq       : sequence number of the NEXT packet sent to this client
#   sent_last : True if the previous tick sent this client a packet
#               (used to set the marker bit after a pause)
sources = {}
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
            s = sources.setdefault(pkt.ssrc, {
                "q": deque(), "started": False, "last": 0.0, "addr": addr,
                "seq": 0, "sent_last": False})
            s["addr"] = addr
            s["q"].append(pcm)
            while len(s["q"]) > MAX_QUEUE:
                s["q"].popleft()
            s["last"] = time.perf_counter()


def make_packet(mix32, contributors, seq, ts, marker):
    """Clip the 32-bit sum to 16 bits, encode as G.711 and wrap it in RTP."""
    out = np.clip(mix32, -32768, 32767).astype(np.int16).tobytes()
    payload = audioop.lin2ulaw(out, 2)
    pkt = RTPPacket(payload, seq=seq, timestamp=ts, ssrc=MIXER_SSRC,
                    csrc=contributors[:15], marker=marker)   # CC field max is 15
    return pkt.pack()


def main(listen_port=5004, dest_host="127.0.0.1", dest_port=5006):
    # dest_host = "clients" -> mix-minus: every client gets its own mix
    to_clients = (dest_host == "clients")
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", listen_port))
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    threading.Thread(target=receiver, args=(rx,), daemon=True).start()
    if to_clients:
        print(f"Mixer listening on {listen_port}, mix-minus back to every client")
    else:
        print(f"Mixer listening on {listen_port}, full mix to {dest_host}:{dest_port}")

    # state for the single-destination (full mix) mode
    single = {"seq": 0, "sent_last": False}

    ts, tick, sent_total = 0, 0, 0
    start = time.perf_counter()
    try:
        while True:
            frames = {}                    # ssrc -> PCM frame that speaks this tick
            now = time.perf_counter()
            with lock:
                clients = []               # (ssrc, state) of every known participant
                for ssrc in list(sources):
                    s = sources[ssrc]
                    if now - s["last"] > TIMEOUT and not s["q"]:
                        del sources[ssrc]
                        continue
                    clients.append((ssrc, s))
                    if not s["started"] and len(s["q"]) >= PREBUFFER:
                        s["started"] = True
                    if s["started"]:
                        if s["q"]:
                            frames[ssrc] = s["q"].popleft().astype(np.int32)
                        else:
                            s["started"] = False

            if frames:
                total = np.sum(list(frames.values()), axis=0)   # sum of ALL speakers
                speakers = list(frames)

                if to_clients:
                    for ssrc, s in clients:
                        # MIX-MINUS: remove this client's own audio from the sum
                        mix = total - frames[ssrc] if ssrc in frames else total
                        csrc = [c for c in speakers if c != ssrc]
                        if not csrc:               # only this client is talking
                            s["sent_last"] = False
                            continue
                        raw = make_packet(mix, csrc, s["seq"], ts,
                                          0 if s["sent_last"] else 1)
                        try:
                            tx.sendto(raw, s["addr"])
                        except OSError:
                            pass
                        s["seq"] += 1
                        s["sent_last"] = True
                        sent_total += 1
                else:
                    raw = make_packet(total, speakers, single["seq"], ts,
                                      0 if single["sent_last"] else 1)
                    try:
                        tx.sendto(raw, (dest_host, dest_port))
                    except OSError:
                        pass
                    single["seq"] += 1
                    single["sent_last"] = True
                    sent_total += 1
            else:
                single["sent_last"] = False
                for _, s in clients:
                    s["sent_last"] = False

            if tick % 50 == 0 and frames:
                print(f"packets_sent={sent_total} speaking={[hex(c) for c in frames]} "
                      f"participants={len(clients)}")
            ts += FRAME                    # the timeline always advances
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