import socket
import sys
import threading
import audioop
import numpy as np
import sounddevice as sd
from rtp import RTPPacket

RATE = 8000
FRAME = 160
PREBUFFER = 3          # frames to collect before playing (60 ms jitter buffer)

buf = bytearray()
lock = threading.Lock()
started = False

def callback(outdata, frames, time_info, status):
    need = frames * 2
    with lock:
        if len(buf) >= need:
            chunk = bytes(buf[:need])
            del buf[:need]
        else:
            chunk = bytes(buf) + b"\x00" * (need - len(buf))   # silence
            buf.clear()
    outdata[:] = np.frombuffer(chunk, dtype=np.int16).reshape(-1, 1)

def main(port=5004):
    global started
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(0.5)
    print(f"Listening on UDP {port} ... Ctrl+C to stop")
    stream = sd.OutputStream(samplerate=RATE, channels=1, dtype="int16",
                             blocksize=FRAME, callback=callback)
    count = 0
    try:
        while True:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            pkt = RTPPacket.unpack(data)
            pcm = audioop.ulaw2lin(pkt.payload, 2)
            with lock:
                buf.extend(pcm)
                ready = len(buf) >= PREBUFFER * FRAME * 2
            if not started and ready:
                stream.start()
                started = True
            count += 1
            if count % 50 == 0:
                print(f"packets={count} seq={pkt.seq} ts={pkt.timestamp} "
                      f"ssrc={pkt.ssrc:#x} csrc={pkt.csrc}")
    except KeyboardInterrupt:
        pass
    finally:
        stream.close()

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5004)