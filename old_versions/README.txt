Earlier versions of mixer.py, kept to show how the mixer evolved.

v1a  mixer_v1a_single_destination.py  one full mix to ONE address (first version)
v1b  mixer_v1b_clients_mode.py         sends the same full mix to every client, own voice included
v2   mixer_v2_mixminus.py              mix-minus: each client gets a mix without its own voice
v3   mixer_v3_jitter.py                per-source jitter buffer ordered by RTP timestamp
v4   mixer_v4_delay.py                 also records how long each packet waits in the mixer
v5   mixer.py (main folder)            adds the summary: CPU and packets per second

Which version produced which evidence:
  v2  Tests 3, 4, 5, 7 and 8 (first runs), and Test 11 (done before the jitter buffer)
  v3  Test 7 rerun and the Test 8 buffer-size comparison
  v4  Tests 9, 10, 12 and 13
  v5  Test 14

To run one of these, copy it next to rtp.py in the main folder first.
