from rtp import RTPPacket

# Test 1: with CSRCs
p = RTPPacket(payload=b"\x7f" * 160, seq=1, timestamp=160,
              ssrc=0xAAAA1111, csrc=[0x1111, 0x2222])
raw = p.pack()
q = RTPPacket.unpack(raw)
assert len(raw) == 12 + 8 + 160
assert (q.seq, q.timestamp, q.ssrc) == (1, 160, 0xAAAA1111)
assert q.csrc == [0x1111, 0x2222]
assert q.payload == p.payload

# Test 2: no CSRCs
p = RTPPacket(payload=b"\x7f" * 160, seq=2, timestamp=320, ssrc=5)
raw = p.pack()
q = RTPPacket.unpack(raw)
assert len(raw) == 12 + 160
assert q.csrc == []

# Test 3: sequence number wraparound
p = RTPPacket(payload=b"", seq=65536, timestamp=0, ssrc=1)
assert p.seq == 0
q = RTPPacket.unpack(RTPPacket(b"", seq=65535, ssrc=1).pack())
assert q.seq == 65535

print("rtp.py OK")