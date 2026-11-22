import struct
import random

class RTPPacket:
    def __init__(self, payload=b"", seq=0, timestamp=0, ssrc=None,
                 csrc=None, pt=0, marker=0):
        self.payload = payload
        self.seq = seq & 0xFFFF
        self.timestamp = timestamp & 0xFFFFFFFF
        self.ssrc = ssrc if ssrc is not None else random.getrandbits(32)
        self.csrc = csrc or []
        self.pt = pt
        self.marker = marker

    def pack(self):
        cc = len(self.csrc)
        byte0 = (2 << 6) | cc              # V=2, P=0, X=0, CC
        byte1 = (self.marker << 7) | self.pt   # M, PT
        header = struct.pack("!BBHII", byte0, byte1,
                             self.seq, self.timestamp, self.ssrc)
        for c in self.csrc:
            header += struct.pack("!I", c)
        return header + self.payload

    @classmethod
    def unpack(cls, data):
        byte0, byte1, seq, ts, ssrc = struct.unpack("!BBHII", data[:12])
        version = byte0 >> 6
        if version != 2:
            raise ValueError("Not an RTP v2 packet")
        cc = byte0 & 0x0F
        csrc = list(struct.unpack(f"!{cc}I", data[12:12 + 4 * cc])) if cc else []
        payload = data[12 + 4 * cc:]
        return cls(payload, seq, ts, ssrc, csrc,
                   pt=byte1 & 0x7F, marker=byte1 >> 7)