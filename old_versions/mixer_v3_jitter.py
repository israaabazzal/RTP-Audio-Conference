"""RTP audio mixer with mix-minus and a per-source jitter buffer.

Run:   python mixer.py 5004 clients                      (mix-minus, 60 ms buffer)
       python mixer.py 5004 clients --buffer-ms 100      (bigger buffer)
       python mixer.py 5004 127.0.0.1 5006               (one full mix to one address)
"""
import socket
import sys
import time
import threading
import audioop
import numpy as np
from rtp import RTPPacket

FRAME = 160            # samples per packet (20 ms at 8 kHz)
PTIME = 0.020
TIMEOUT = 5.0          # forget a source after 5 s without packets
MIXER_SSRC = 0x4D495852
DEFAULT_BUFFER_MS = 60 # jitter buffer depth: how long we wait for late packets
MISS_LIMIT = 10        # empty ticks (200 ms) before a source counts as 'paused'
MAX_GAP = 10           # a jump bigger than this many frames is a new talk-spurt
MAX_AHEAD = 10         # extra frames allowed above the buffer depth before we skip ahead


class JitterBuffer:
    """Holds the packets of ONE source and hands them out in RTP-timestamp order.

    Each packet gets a slot number: (timestamp - first timestamp) / 160.
    Once per 20 ms tick the mixer calls pop() and gets the frame for the next slot.
    """

    def __init__(self, depth_frames):
        self.depth = max(1, depth_frames)
        self.frames = {}        # slot number -> PCM frame
        self.base_ts = None     # timestamp of the first packet (slot 0)
        self.next_idx = 0       # slot to play on the next tick
        self.max_idx = None     # highest slot received so far
        self.started = False
        self.pending = 0        # empty ticks in a row (counted only if the source returns)
        # statistics for the report
        self.received = self.lost = self.underrun = 0
        self.late = self.dup = self.reordered = 0
        self.overruns = self.resyncs = 0

    def slot_of(self, ts):
        if self.base_ts is None:
            self.base_ts = ts
        d = (ts - self.base_ts) & 0xFFFFFFFF
        if d >= 0x80000000:              # timestamp earlier than the first one
            d -= 0x100000000
        return d // FRAME                # also correct across the 32-bit wrap-around

    def push(self, ts, pcm):
        idx = self.slot_of(ts)
        self.received += 1
        if self.started and idx < self.next_idx:
            self.late += 1               # its turn already passed
            return
        if idx in self.frames:
            self.dup += 1
            return
        if self.max_idx is not None and idx < self.max_idx:
            self.reordered += 1          # arrived after a newer packet
        self.frames[idx] = pcm
        if self.max_idx is None or idx > self.max_idx:
            self.max_idx = idx

    def _reset(self):
        self.started = False
        self.frames.clear()
        self.max_idx = None
        self.pending = 0

    def pop(self):
        """Called once every 20 ms. Returns a PCM frame, or None (nothing to play)."""
        if not self.started:
            if len(self.frames) < self.depth:
                return None              # still filling the buffer
            self.next_idx = min(self.frames)
            self.started = True
            self.pending = 0

        # the source runs far ahead of us: skip forward instead of building delay
        if self.frames and self.max_idx - self.next_idx > self.depth + MAX_AHEAD:
            new_next = self.max_idx - self.depth + 1
            self.overruns += new_next - self.next_idx
            for k in [k for k in self.frames if k < new_next]:
                del self.frames[k]
            self.next_idx = new_next

        # a big hole before the next packet: new talk-spurt, jump to it
        if self.frames and min(self.frames) - self.next_idx > MAX_GAP:
            self.next_idx = min(self.frames)
            self.resyncs += 1

        frame = self.frames.pop(self.next_idx, None)
        self.next_idx += 1
        if frame is not None:
            self.underrun += self.pending
            self.pending = 0
            return frame
        if self.frames:                  # newer packets exist -> this one was lost
            self.lost += 1
        else:                            # buffer empty -> late or source paused
            self.pending += 1
            if self.pending > MISS_LIMIT:
                self._reset()            # treat as paused; refill before next play
        return None

    def stats(self):
        return dict(received=self.received, lost=self.lost, underrun=self.underrun,
                    late=self.late, dup=self.dup, reordered=self.reordered,
                    overruns=self.overruns, resyncs=self.resyncs)


# ssrc -> {"jb", "last", "addr", "seq", "sent_last"}
sources = {}
history = {}            # stats of sources that already left
lock = threading.Lock()
BUFFER_FRAMES = 3


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
                "jb": JitterBuffer(BUFFER_FRAMES), "last": 0.0, "addr": addr,
                "seq": 0, "sent_last": False})
            s["addr"] = addr
            s["jb"].push(pkt.timestamp, pcm)
            s["last"] = time.perf_counter()


def make_packet(mix32, contributors, seq, ts, marker):
    """Clip the 32-bit sum to 16 bits, encode as G.711 and wrap it in RTP."""
    out = np.clip(mix32, -32768, 32767).astype(np.int16).tobytes()
    payload = audioop.lin2ulaw(out, 2)
    pkt = RTPPacket(payload, seq=seq, timestamp=ts, ssrc=MIXER_SSRC,
                    csrc=contributors[:15], marker=marker)   # CC field max is 15
    return pkt.pack()


def print_report():
    rows = dict(history)
    with lock:
        for ssrc, s in sources.items():
            rows[ssrc] = s["jb"].stats()
    print("\n--- jitter buffer report (per source) ---")
    print(f"{'source':<12}{'recv':>6}{'lost':>6}{'underrun':>9}{'late':>6}"
          f"{'dup':>5}{'reorder':>8}{'overrun':>8}{'resync':>7}")
    for ssrc, st in rows.items():
        print(f"0x{ssrc:08x}{st['received']:>6}{st['lost']:>6}{st['underrun']:>9}"
              f"{st['late']:>6}{st['dup']:>5}{st['reordered']:>8}"
              f"{st['overruns']:>8}{st['resyncs']:>7}")


def main(listen_port=5004, dest_host="127.0.0.1", dest_port=5006):
    # dest_host = "clients" -> mix-minus: every client gets its own mix
    to_clients = (dest_host == "clients")
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("0.0.0.0", listen_port))
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    threading.Thread(target=receiver, args=(rx,), daemon=True).start()
    what = "mix-minus back to every client" if to_clients else f"full mix to {dest_host}:{dest_port}"
    print(f"Mixer listening on {listen_port}, {what}, "
          f"jitter buffer {BUFFER_FRAMES * 20} ms")

    single = {"seq": 0, "sent_last": False}   # state for the single-destination mode
    ts, tick, sent_total = 0, 0, 0
    start = time.perf_counter()
    try:
        while True:
            frames = {}                    # ssrc -> PCM frame that plays this tick
            now = time.perf_counter()
            with lock:
                clients = []
                for ssrc in list(sources):
                    s = sources[ssrc]
                    jb = s["jb"]
                    if now - s["last"] > TIMEOUT and not jb.frames:
                        history[ssrc] = jb.stats()
                        del sources[ssrc]
                        continue
                    clients.append((ssrc, s))
                    f = jb.pop()
                    if f is not None:
                        frames[ssrc] = f.astype(np.int32)

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
        print_report()


if __name__ == "__main__":
    args = sys.argv[1:]
    buffer_ms = DEFAULT_BUFFER_MS
    if "--buffer-ms" in args:
        i = args.index("--buffer-ms")
        buffer_ms = int(args[i + 1])
        del args[i:i + 2]
    BUFFER_FRAMES = max(1, round(buffer_ms / 20))
    main(int(args[0]) if len(args) > 0 else 5004,
         args[1] if len(args) > 1 else "127.0.0.1",
         int(args[2]) if len(args) > 2 else 5006)