# RTP-Based Multi-Source Audio Conferencing System

Proposal 1: several users send audio to a central **RTP mixer**. The mixer combines the streams and sends mixed audio back to every participant, listing who is speaking.

```
 Client A ──┐                                   ┌── mix without A's voice ──> Client A
 Client B ──┼── RTP/UDP (G.711, 20 ms) ──> MIXER ┼── mix without B's voice ──> Client B
 Client C ──┘   each has its own SSRC           └── mix without C's voice ──> Client C
                                           (mixer SSRC + CSRC list of the speakers)
```

## What it does
- **Own RTP implementation** (`rtp.py`): builds and reads the RTP header by hand (version, CSRC count, marker, payload type, sequence, timestamp, SSRC, CSRC list).
- **Unique 32-bit SSRC** for every participant (random).
- **G.711 (PCMU, payload type 0)**, 8 kHz, 20 ms packets (160 samples), over UDP.
- **Mixer with mix-minus:** each client hears everyone except itself. Each packet carries the mixer's SSRC and a **CSRC list** of the other speakers.
- **Jitter buffer per source, ordered by RTP timestamp:** fixes reordering and duplicates, and keeps timing when a packet is lost. Size is set with `--buffer-ms` (default 60 ms).
- **Client playout by RTP timestamp:** lost packets become silence, late and duplicate packets are dropped.
- **Measurements:** the mixer prints a report with lost, late, duplicate and reordered packets, its own delay, CPU use and packets per second.

## Setup (Windows)
Use **Python 3.11** (the code uses `audioop`, which was removed in Python 3.13).

```
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```
Tested with numpy 2.4.6, scipy 1.17.1, sounddevice 0.5.6 and matplotlib 3.11.2. Wireshark is used for the packet captures.

In the commands below, `python` means `venv\Scripts\python.exe`. Run everything from the project folder. Use a **headset** for live microphone tests, otherwise the speakers feed back into the microphone.

## How to run
**1. Conference with mix-minus (the main mode).** Start the mixer first, then the clients:
```
python mixer.py 5004 clients                       # mixer, jitter buffer 60 ms
python mixer.py 5004 clients --buffer-ms 120       # bigger jitter buffer
python client.py 127.0.0.1 tone440.wav             # client sending a WAV file
python client.py 127.0.0.1 mic                     # client using the microphone (Ctrl+C to stop)
python client.py 127.0.0.1 tone440.wav 0 10        # 10% of incoming packets dropped on purpose (0 = whole file)
python launch_clients.py 6                         # start 6 test clients at once
```
Press `Ctrl+C` in the mixer window to print its report.

**2. Two laptops.** On the mixer laptop find the IP with `ipconfig` and allow Python through the firewall for **UDP 5004**. Start the mixer there, then on each laptop:
```
python client.py <mixer_ip> mic
```

**3. Single-destination mode** (one full mix to one address, used for the first tests):
```
python mixer.py 5004 127.0.0.1 5006
python send_wav.py tone440.wav                     # a source: file [port] [host] [loss %]
python send_wav.py tone440.wav 5004 127.0.0.1 5    # same, dropping 5% of its packets
python receive_play.py 5006                        # simple listener that plays the mix
```

**4. Tests and tools**
```
python test_rtp.py                    # unit test of the RTP code (prints "rtp.py OK")
python send_one.py                    # one packet with 2 CSRC values, for Wireshark
python sync_test.py                   # synchronization test (mixer in single-destination mode first)
python make_wav.py tone440.wav 440    # make a 10 s test tone
python make_charts.py                 # redraw the 9 report charts in the folder "charts"
```

## Files
| File | Purpose |
|---|---|
| `rtp.py` | RTP packet building and parsing |
| `mixer.py` | The mixer (mix-minus, jitter buffer, report) |
| `client.py` | Client: sends a file or the microphone, plays the mix, prints a playout report |
| `launch_clients.py` | Starts several test clients at once |
| `send_wav.py`, `send_one.py`, `receive_play.py` | Simple sender, one-packet sender and listener (first tests) |
| `sync_test.py` | Measures synchronization of two sources |
| `make_wav.py`, `record_wav.py`, `mic_test.py` | Make tones, record voices, test the microphone |
| `make_charts.py`, `charts/` | Report charts, drawn from the measured numbers |
| `test_rtp.py` | RTP unit test |
| `old_versions/` | Earlier mixer versions (v2, v3, v4), see its README |
| `evidence/` | Screenshots and captures of every test (kept locally, not uploaded to GitHub) |

## Tests and results (more detail in `evidence/`)
| Test | What it shows | Result |
|---|---|---|
| 1 to 3 | RTP code, one packet, one source through the mixer | Header correct, 500 of 500 packets, 0 lost |
| 4 | Two sources | CSRC count goes 1, 2, 1. Mixer stream 0 lost |
| 5 | 5% loss set on one source | 6.4% measured (random). Other streams 0% |
| 6 | Jitter (no run of its own, read from the tables of Tests 4, 7 and 8) | Tone clients mean 0.30 to 0.65 ms, mixer output 0.26 to 0.59 ms, live mic about 20 ms |
| 7, 10 | 3 and 4 clients with mix-minus | Each client's CSRC list has the others, never itself. 0 lost |
| 8 | Live microphone | Mic jitter about 20 ms (driver bursts), 0 lost |
| 9 | Late join and early leave | CSRC list follows who is talking. 0 lost, 0 late |
| 11 | Loss at 0%, 5%, 10% at the client | Every lost packet detected and filled with silence |
| 12 | Latency | Mixer delay 14.4 / 40.2 / 101.5 ms for 20 / 60 / 120 ms buffers |
| 13 | Synchronization | Error within 30 ms (about one packet). Clock drift under 2 ms in 4 s |
| 14 | Scaling, 2 to 8 clients | Delay flat at 50 to 54 ms, CPU 3 to 11% of one core, 0 lost |

## Known limits
- Most tests ran on one computer, so real network loss and reordering are only shown by the two-laptop test.
- Different sources are lined up by when their first packet arrives. Exact alignment would need RTCP sender reports. There is no RTCP at all.
- The jitter buffer has a fixed size. There is no encryption (SRTP) and no NAT traversal.
- A client that leaves is noticed only after the mixer's 5 second timeout.
- Mixing adds the samples and clips them to 16 bits (no scaling), and audio devices are the Windows defaults.
