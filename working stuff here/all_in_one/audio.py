# audio.py
import logging
import platform
import socket
import subprocess
import time 
import pyaudio 
import threading
from config import app_config

PORT = 50009
CHUNK_SIZE = 2048
RATE = 44100
CHANNELS = 1
s = None
tries = 10 
VIRTUAL_CABLE_DEVICE = "CABLE Output" 

def cleanup():
    global s
    try:
        s.shutdown(socket.SHUT_RDWR)
    except:
        print("yesh")
        logging.info(f"[Audio] Stopped")

def run_audio_receiver():

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', PORT))
    s.listen(1)
    print("Audio waiting")

    conn, addr = s.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print("Audio Connected by", addr)
    logging.info("[Audio] Connected")

    try:
        while True:
            data = conn.recv(CHUNK_SIZE * 2)
            if not data:
                break
            stream.write(data)
    except KeyboardInterrupt:
        print("Server interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        conn.close()
        s.close()

def run_audio_sender_windows():
    # Find the virtual audio cable device index
    device_index = None
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if VIRTUAL_CABLE_DEVICE in device_info.get('name'):
            device_index = i
            break

    if device_index is None:
        raise RuntimeError(f"[Audio] Could not find device: {VIRTUAL_CABLE_DEVICE}")

    device_info = p.get_device_info_by_index(device_index)
    if device_info['maxInputChannels'] < 1:
        raise RuntimeError(f"[Audio] Device '{VIRTUAL_CABLE_DEVICE}' does not support input channels.")
    
    
    
    # Connect to receiver
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    c = tries
    while c != 0:
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            logging.info(f"[Audio] Connection Attempt: {c}")
            print(f"[Audio] Connection Attempt: {c}")
            time.sleep(1)
            c -= 1
            if c == 0:
                logging.info(f"[Audio] Failed to connect: {e}")
                print(f"[Audio] Failed to connect: {e}")
                return

    # Open PyAudio stream
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    print("[Audio] Streaming from Virtual Cable...")
    logging.info("[Audio] Streaming from Virtual Cable...")

    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("[Audio] Audio streaming interrupted.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        s.close()

def run_audio_sender_linux():
    def get_default_monitor():
        result = subprocess.run(["pactl", "get-default-sink"], stdout=subprocess.PIPE, text=True)
        default_sink = result.stdout.strip()
        if not default_sink:
            raise RuntimeError("Could not determine default audio sink.")
        return f"{default_sink}.monitor"

    def mute_output():
        subprocess.run(["pactl", "set-sink-mute", "0", "1"])

    def unmute_output():
        subprocess.run(["pactl", "set-sink-mute", "0", "0"])

    monitor_source = get_default_monitor()
    mute_output()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    c = tries
    while c!=0:
        try:
            s.connect((app_config.audio_ip, PORT))
            break
        except Exception as e:
            logging.info(f"[Audio] Connection Attempt: {c}")
            print(f"[Audio] Connection Attempt: {c}")
            time.sleep(1)
            c-=1
            if c == 0:
                logging.info(f"[Audio] Failed to connect: {e}")
                print(f"[Audio] Failed to connect: {e}")
                return 
    print("Audio Connected to server.")
    logging.info("[Audio] Streaming audio...")

    parec_cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]
    proc = subprocess.Popen(parec_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.sendall(data)
    except KeyboardInterrupt:
        print("Audio stopped.")
        logging.info("[Audio] Streaming stopped.")
    finally:
        proc.terminate()
        unmute_output()
        s.close()


def main():
    os_type = platform.system().lower()
    
    if app_config.audio_mode == "Share_Audio":
        if "windows" in os_type:
            run_audio_sender_windows()
        elif "linux" in os_type:
            run_audio_sender_linux()
    elif app_config.audio_mode == "Receive_Audio":
        run_audio_receiver()

    def monitor_stop():
            while app_config.is_running and not app_config.stop_flag:
                time.sleep(0.5)
            cleanup()
    threading.Thread(target=monitor_stop, daemon=True).start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a",format ="%(levelname)s - %(message)s")
    main()
