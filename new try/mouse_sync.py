import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
from pynput import mouse

class MouseSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mouse Sync")
        self.root.geometry("300x400")

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        print(f"[System] Screen dimensions: {self.screen_width}x{self.screen_height}")

        self.is_server = tk.BooleanVar(value=False)
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.port = 50007
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_controller = mouse.Controller()
        self.overlay = None

        self.setup_gui()

    def setup_gui(self):
        mode_frame = ttk.LabelFrame(self.root, text="Mode", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)

        ttk.Radiobutton(mode_frame, text="Server", variable=self.is_server,
                        value=True, command=self.update_mode).pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Client", variable=self.is_server,
                        value=False, command=self.update_mode).pack(side="left", padx=5)

        ip_frame = ttk.LabelFrame(self.root, text="Server IP", padding=10)
        ip_frame.pack(fill="x", padx=10, pady=5)

        self.ip_entry = ttk.Entry(ip_frame, textvariable=self.server_ip)
        self.ip_entry.pack(fill="x", padx=5, pady=5)

        screen_frame = ttk.LabelFrame(self.root, text="Screen Info", padding=10)
        screen_frame.pack(fill="x", padx=10, pady=5)

        self.screen_label = ttk.Label(screen_frame,
                                      text=f"Screen: {self.screen_width}x{self.screen_height}")
        self.screen_label.pack(fill="x", padx=5, pady=5)

        self.start_button = ttk.Button(self.root, text="Start", command=self.toggle_connection)
        self.start_button.pack(pady=10)

        self.status_label = ttk.Label(self.root, text="Status: Disconnected")
        self.status_label.pack(pady=5)

        self.update_mode()

    def update_mode(self):
        self.ip_entry.config(state="disabled" if self.is_server.get() else "normal")
        print(f"[Mode] Switched to {'Server' if self.is_server.get() else 'Client'} mode")

    def toggle_connection(self):
        if not self.is_running:
            self.start_connection()
        else:
            self.stop_connection()

    def start_connection(self):
        try:
            if self.is_server.get():
                self.start_server()
            else:
                self.start_client()
            self.is_running = True
            self.start_button.config(text="Stop")
            self.status_label.config(text="Status: Connected")
        except Exception as e:
            print(f"[Error] Connection failed: {str(e)}")
            messagebox.showerror("Error", f"Failed to start: {str(e)}")

    def stop_connection(self):
        print("[System] Stopping connection...")
        self.is_running = False

        if self.overlay:
            try:
                self.overlay.destroy()
            except:
                pass
            self.overlay = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Disconnected")
        print("[System] Connection stopped")

    def create_overlay(self):
        print("[Overlay] Creating full-screen transparent overlay")
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        self.overlay.attributes("-alpha", 0.01)
        self.overlay.configure(bg="black")
        self.overlay.config(cursor="none")
        self.overlay.lift()
        self.overlay.focus_force()
        self.overlay.update_idletasks()
        print("[Overlay] Overlay is now active and covering full screen")

    def handle_client(self, client_socket):
        print("[Server] Starting raw mouse delta tracking...")
        self.root.after(0, self.create_overlay)

        last_position = [None]

        def on_move(x, y):
            if not self.is_running:
                return False
            if last_position[0] is None:
                last_position[0] = (x, y)
                return
            last_x, last_y = last_position[0]
            dx = x - last_x
            dy = y - last_y
            last_position[0] = (x, y)
            if dx or dy:
                try:
                    data = json.dumps({"dx": dx, "dy": dy}) + '\n'
                    client_socket.sendall(data.encode())
                except Exception as e:
                    print(f"[Server] Send error: {e}")
                    self.stop_connection()
                    return False

        def listener_thread():
            print("[Server] Mouse listener thread started")
            with mouse.Listener(on_move=on_move) as listener:
                listener.join()

        threading.Thread(target=listener_thread, daemon=True).start()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(1)
        print(f"[Server] Listening on port {self.port}")

        def server_thread():
            try:
                print("[Server] Waiting for client...")
                client, addr = self.server_socket.accept()
                print(f"[Server] Client connected: {addr}")
                client.sendall(b'CONNECTED\n')
                self.handle_client(client)
            except Exception as e:
                if self.is_running:
                    print(f"[Server] Error: {e}")
                self.stop_connection()

        threading.Thread(target=server_thread, daemon=True).start()

    def start_client(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_ip.get(), self.port))
        print(f"[Client] Connected to server {self.server_ip.get()}:{self.port}")

        data = self.client_socket.recv(1024)
        if data != b'CONNECTED\n':
            raise Exception("Failed handshake with server")

        def client_thread():
            print("[Client] Receiving mouse movements...")
            buffer = ""
            while self.is_running:
                try:
                    data = self.client_socket.recv(1024).decode()
                    if not data:
                        print("[Client] Server closed connection")
                        break
                    buffer += data
                    while '\n' in buffer:
                        msg, buffer = buffer.split('\n', 1)
                        try:
                            delta = json.loads(msg)
                            self.mouse_controller.move(delta['dx'], delta['dy'])
                        except Exception as e:
                            print(f"[Client] Error parsing delta: {e}")
                except Exception as e:
                    if self.is_running:
                        print(f"[Client] Error: {e}")
                    break

        threading.Thread(target=client_thread, daemon=True).start()

    def on_closing(self):
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseSyncApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
