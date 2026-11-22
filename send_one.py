import socket
from rtp import RTPPacket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
p = RTPPacket(b"\xff" * 160, seq=1, timestamp=160, csrc=[111, 222])
s.sendto(p.pack(), ("127.0.0.1", 5004))
print("sent")