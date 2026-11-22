import socket
import sys
import time
import queue
import random
import threading
import audioop
import numpy as np
import sounddevice as sd
from rtp import RTPPacket
from send_wav import load_pcm

RATE = 8000
FRAME = 160            # 20 ms at 8 kHz
PTIME = 0.020
PREBUFFER = 3          # frames to collect before playing (60 ms)
MAX_AHEAD = 8          # if we fall 8 frames behind, jump forward (resync)
MIXER_PORT = 5004
SILENCE = b"\x00" * (FRAME * 2)

lock = threading.Lock()
frames = {}            # playout index -> PCM bytes (index = timestamp position)
out_buf = bytearray()
st = {"base_ts": None, "next_idx": 0, "latest_idx": -1, "started": False,
      "last_seq": None, "last_rx": 0.0, "received": 0, "lost": 0,
      "late": 0, "dup": 0, "played": 0, "gap_filled": 0, "idle": 0,
      "resync": 0, "dropped_on_purpose": 0}

def next_frame():
    """Called with the lock held: the frame that belongs at this moment."""
    idx = st["next_idx"]
    data = frames.pop(idx, None)
    if data is not None:
        st["played"] += 1
    else:
        data = SILENCE
        if idx <= st["latest_idx"]:
            st["gap_filled"] += 1      # a frame we expected never arrived in time
        else:
            st["idle"] += 1            # nothing newer yet, just waiting
    st["next_idx"] = idx + 1
    return data

def play_callback(outdata, frames_n, time_info, status):
    need = frames_n * 2
    with lock:
        while len(out_buf) < need:
            out_buf.extend(next_frame())
        chunk = bytes(out_buf[:need])
        del out_buf[:need]
    outdata[:] = np.frombuffer(chunk, dtype=np.int16).reshape(-1, 1)

def store_packet(pkt, pcm):
    """Place one packet on the playout timeline using its RTP timestamp."""
    with lock:
        if st["base_ts"] is None:
            st["base_ts"] = pkt.timestamp
        d = ((pkt.timestamp - st["base_ts"] + 2 ** 31) & 0xFFFFFFFF) - 2 ** 31
        idx = d // FRAME
        # loss detection from sequence numbers
        if st["last_seq"] is not None:
            diff = (pkt.seq - st["last_seq"]) & 0xFFFF
            if 0 < diff < 32768:
                st["lost"] += diff - 1
                st["last_seq"] = pkt.seq
        else:
            st["last_seq"] = pkt.seq
        st["received"] += 1
        if idx < st["next_idx"]:
            st["late"] += 1            # too late: its moment has passed
            return False
        if idx in frames:
            st["dup"] += 1             # duplicate
            return False
        frames[idx] = pcm
        if idx > st["latest_idx"]:
            st["latest_idx"] = idx
        if st["latest_idx"] - st["next_idx"] > MAX_AHEAD:
            new_next = st["latest_idx"] - PREBUFFER + 1
            for k in [k for k in frames if k < new_next]:
                del frames[k]
            st["next_idx"] = new_next
            st["resync"] += 1
        return len(frames) >= PREBUFFER

def receive_loop(sock, stream, stop, drop):
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        except ConnectionResetError:
            continue                      # Windows: mixer was not running yet
        except OSError:
            break
        if drop and random.random() * 100 < drop:
            st["dropped_on_purpose"] += 1   # simulated loss on the way back
            continue
        try:
            pkt = RTPPacket.unpack(data)
        except Exception:
            continue
        pcm = audioop.ulaw2lin(pkt.payload, 2)
        ready = store_packet(pkt, pcm)
        if not st["started"] and ready:
            stream.start()
            st["started"] = True
        st["last_rx"] = time.perf_counter()
        if st["received"] % 50 == 0:
            print(f"heard mix: packets={st['received']} seq={pkt.seq} "
                  f"ssrc={pkt.ssrc:#x} csrc={pkt.csrc}")

def report():
    with lock:
        s = dict(st)
    print("--- playout report ---")
    print(f"packets received:            {s['received']}")
    print(f"dropped on purpose:          {s['dropped_on_purpose']}")
    print(f"lost (gaps in sequence):     {s['lost']}")
    print(f"late (dropped):              {s['late']}")
    print(f"duplicates (dropped):        {s['dup']}")
    print(f"frames played:               {s['played']}")
    print(f"gaps filled with silence:    {s['gap_filled']}")
    print(f"idle (nothing to play yet):  {s['idle']}")
    print(f"resyncs:                     {s['resync']}")

def send_file(sock, dest, path, ssrc):
    pcm = load_pcm(path)
    seq, ts = 0, 0
    start = time.perf_counter()
    n = len(pcm) // FRAME
    for i in range(n):
        frame = pcm[i * FRAME:(i + 1) * FRAME].tobytes()
        payload = audioop.lin2ulaw(frame, 2)
        pkt = RTPPacket(payload, seq=seq, timestamp=ts, ssrc=ssrc,
                        marker=1 if i == 0 else 0)
        sock.sendto(pkt.pack(), dest)
        seq += 1
        ts += FRAME
        wait = start + (i + 1) * PTIME - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
    return n

def send_mic(sock, dest, ssrc, seconds):
    q = queue.Queue()

    def cb(indata, frames_n, time_info, status):
        q.put(indata.copy().tobytes())

    seq, ts, count = 0, 0, 0
    end = time.perf_counter() + seconds if seconds else None
    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                        blocksize=FRAME, callback=cb):
        while end is None or time.perf_counter() < end:
            try:
                frame = q.get(timeout=0.5)
            except queue.Empty:
                continue
            payload = audioop.lin2ulaw(frame, 2)
            pkt = RTPPacket(payload, seq=seq, timestamp=ts, ssrc=ssrc,
                            marker=1 if count == 0 else 0)
            sock.sendto(pkt.pack(), dest)
            seq += 1
            ts += FRAME
            count += 1
    return count

def main(host, source, seconds=None, drop=0.0):
    dest = (host, MIXER_PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 0))             # same socket sends and receives
    sock.settimeout(0.5)
    ssrc = random.getrandbits(32)
    stream = sd.OutputStream(samplerate=RATE, channels=1, dtype="int16",
                             blocksize=FRAME, callback=play_callback)
    stop = threading.Event()
    threading.Thread(target=receive_loop, args=(sock, stream, stop, drop),
                     daemon=True).start()
    print(f"Client SSRC={ssrc:#x}, sending '{source}' to {host}:{MIXER_PORT}"
          + (f", dropping {drop}% of incoming packets" if drop else ""))
    try:
        if source.lower() == "mic":
            print("Speaking into the microphone. Ctrl+C to stop. Use a headset!")
            n = send_mic(sock, dest, ssrc, seconds)
        else:
            n = send_file(sock, dest, source, ssrc)
        print(f"Finished sending {n} packets. Listening to the rest of the conference...")
        t0 = time.perf_counter()
        while True:
            time.sleep(0.2)
            now = time.perf_counter()
            if st["received"] == 0 and now - t0 > 3:
                print("Nothing came back from the mixer. Is it running with 'clients'?")
                break
            if st["received"] > 0 and now - st["last_rx"] > 1.5:
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        stream.close()
        sock.close()
    report()
    print("Client stopped")

if __name__ == "__main__":
    # python client.py <mixer_ip> <file.wav | mic> [seconds] [drop percent]
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 0
    main(sys.argv[1], sys.argv[2],
         secs if secs > 0 else None,
         float(sys.argv[4]) if len(sys.argv) > 4 else 0.0)