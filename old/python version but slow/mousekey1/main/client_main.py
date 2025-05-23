### ✅ FIXED: client_main.py

from net.client import Client
from clipboard.clipboard_manager import watch_clipboard
from input.input_listener import InputListener
from input.input_controller import handle_input_event  # <-- added
from common.protocol import encode_event
import sys
import pickle
import platform
import threading
from pynput.mouse import Controller

if platform.system() == "Windows":
    import ctypes
    def get_screen_width():
        return ctypes.windll.user32.GetSystemMetrics(0)
else:
    from Xlib import display
    def get_screen_width():
        d = display.Display()
        screen = d.screen()
        return screen.width_in_pixels

def receive_events(client):
    while True:
        data = client.receive()
        if not data:
            continue
        try:
            event = pickle.loads(data)
            if event.get("type") == "switch":
                print(f"[Client] Mouse switched from: {event['edge']}")
                screen_width = get_screen_width()
                mouse = Controller()
                if event['edge'] == "right":
                    print("\u2192 Moving to left edge: (0, 100)")
                    mouse.position = (0, 100)
                elif event['edge'] == "left":
                    print(f"\u2192 Moving to right edge: ({screen_width - 1}, 100)")
                    mouse.position = (screen_width - 1, 100)
            else:
                handle_input_event(event)  # <-- NEW: apply server input

        except Exception as e:
            print(f"[Client] Error processing data: {e}")

if __name__ == "__main__":
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    client = Client(server_ip=server_ip)
    client.connect()

    print("[Client] Starting input listener and clipboard watcher...")

    threading.Thread(target=receive_events, args=(client,), daemon=True).start()

    listener = InputListener(send_callback=client.send)
    listener.start()

    watch_clipboard(lambda event: client.send(encode_event(event)))

    try:
        while True:
            pass
    except KeyboardInterrupt:
        client.close()
