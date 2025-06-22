import socket
import subprocess
import platform
import time
import logging
import threading
import pyaudio
from config import app_config

PORT = 50009
CHUNK_SIZE = 1024
RATE = 44100 
CHANNELS = 1
VIRTUAL_CABLE_DEVICE = "CABLE Output"

logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a", format="[Audio] - %(message)s")

def cleanup(sock=None, process=None, unmute=False):
    try:
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception as e:
                logging.error(f"⚠️ Error terminating process: {e}")
        if sock:
            try:
                sock.close()
            except Exception as e:
                logging.error(f"⚠️ Error closing socket: {e}")
    finally:
        logging.info("Cleaned up audio resources.")

def receive_audio():
    
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK_SIZE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', PORT))

    print("🔊 Receiving audio...")
    logging.info("[Audio] Listening...")
    try:
        while True:
            data, _ = sock.recvfrom(CHUNK_SIZE)
            stream.write(data)
    except KeyboardInterrupt:
        print("❌ Receiver stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        sock.close()

def send_audio_linux():
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
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # for _ in range(5,0,-1):
    #     try:
    #         s.connect((app_config.audio_ip, PORT))
    #         break
    #     except Exception as e:
    #         time.sleep(1)
    # else:
    #     logging.info(f"[Audio] Failed to connect: {e}")
    #     print(f"[Audio] Failed to connect: {e}")
    #     return 
    
    print("Audio Connected to server.")
    logging.info("[Audio] Streaming audio...")

    parec_cmd = ["parec", "--format=s16le", "--rate=44100", "--channels=1", "-d", monitor_source]
    proc = subprocess.Popen(parec_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = proc.stdout.read(CHUNK_SIZE)
            if not data:
                break
            s.sendto(data,(app_config.audio_ip,PORT))
    except KeyboardInterrupt:
        print("Audio stopped.")
        logging.info("[Audio] Streaming stopped.")
    finally:
        proc.terminate()
        unmute_output()
        s.close()

def send_audio_windows():

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
    stream = p.open(format=pyaudio.paInt16,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK_SIZE)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print("📤 Sending audio from VB-Cable...")
    try:
        while True:
            data = stream.read(CHUNK_SIZE)
            sock.sendto(data, (app_config.audio_ip, PORT))
    except KeyboardInterrupt:
        print("❌ Sender stopped.")
    finally:
        sock.close()

def main():
    def monitor_stop():
        while True:
            if not app_config.is_running:
                cleanup()
                break
            time.sleep(1)

    threading.Thread(target=monitor_stop, daemon=True).start()

    os_type = platform.system().lower()
    if app_config.audio_mode == "Receive_Audio":
        receive_audio()
    elif app_config.audio_mode == "Share_Audio":
        if os_type == "linux":
            send_audio_linux()
        elif os_type == "windows":
            send_audio_windows()
        else:
            print(f"❌ Unsupported OS: {os_type}")
            logging.info("Unsupported OS")
    else:
        print("❌ Invalid audio_mode in config.")
        logging.info("Invalid audio_mode in config.")

if __name__ == "__main__":
    main()
