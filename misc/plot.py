import sys
import socket
import threading
import queue
import time

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import matplotlib.style as mplstyle
mplstyle.use('fast')

CHUNK_SECS = 0.25
SAMPLE_RATE = 48000
CHAN_COUNT = 8

def connect(addr, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((addr, port))
    return sock

def recv_thread_fn(recv_q, sock):
    while True:
        received_bits = []
        received_len = 0
        receive_total = int(SAMPLE_RATE*CHUNK_SECS)*CHAN_COUNT*2
        while received_len < receive_total:
            more = sock.recv(min(4096, receive_total-received_len))
            received_bits.append(more)
            received_len += len(more)
        receive_chunk = np.frombuffer(b"".join(received_bits), dtype=np.uint8)
        receive_chunk = receive_chunk.view(np.int16)
        receive_chunk.shape = (int(SAMPLE_RATE*CHUNK_SECS), CHAN_COUNT)
        try:
            time.sleep(0.01)
            recv_q.put_nowait(receive_chunk)
        except queue.Full:
            pass

def animate(i):
    global recv_q
    bit = recv_q.get()
    for p in range(CHAN_COUNT):
        plt.subplot(CHAN_COUNT, 1, p+1)
        plt.cla()
        plt.plot(range(len(bit)), bit[:, p])
        plt.ylim([-32768, 32767])
        plt.title(f"{i}, {p}")

def main():
    global recv_q
    recv_q = queue.Queue(maxsize=3)
    sock = connect(sys.argv[1], int(sys.argv[2]))
    recv_thread = threading.Thread(target=recv_thread_fn, args=(recv_q, sock),
        daemon=True)
    recv_thread.start()

    fig = plt.figure()
    anim = FuncAnimation(fig, animate, interval=1000*CHUNK_SECS,
        cache_frame_data=False)
    plt.show()

if __name__ == "__main__":
    main()
