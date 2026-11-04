import socket
import threading

def forward(src, dst):
    try:
        while True:
            data = src.recv(8192)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass

def handle_client(client_sock):
    target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        target_sock.connect(('127.0.0.1', 5173))
        t1 = threading.Thread(target=forward, args=(client_sock, target_sock), daemon=True)
        t2 = threading.Thread(target=forward, args=(target_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
    except Exception:
        try:
            client_sock.close()
        except Exception:
            pass

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 5174))
    server.listen(50)
    print("Port bridge 5174 -> 5173 active on 0.0.0.0:5174.")
    while True:
        try:
            client_sock, _ = server.accept()
            threading.Thread(target=handle_client, args=(client_sock,), daemon=True).start()
        except Exception:
            pass

if __name__ == '__main__':
    main()

