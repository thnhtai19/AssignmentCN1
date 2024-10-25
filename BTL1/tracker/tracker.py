import socket
import threading
import mysql.connector as mysql
import json
import os
import random

TRACKER_PORT = 50000
TRACKER_ADDRESS = "127.0.0.1" #Random IP  :vvv

con = mysql.connect(host="localhost", user="root", password="", database="computer_network")
cursor=con.cursor()
# cursor.execute("Some query"")

living_conn = []
public_key, private_key = None, None

def view_peers():
    print("view_peers")

def ping():
    print("ping")

def client_handler(conn, addr):
    global public_key
    conn.sendall(json.dumps({"public_key": public_key}).encode())
    print(f"[INFO] Sent public key to client at {addr}")
    login(conn, addr)
    while True:
        req = conn.recv(4096).decode()
        if not req:
            break
        
        # Determine request
        request = json.loads(req)
        req_option = request['option']
        ip = addr[0]
        port = request['peers_port'] if 'peers_port' in request else ""
        hostname = request['peers_hostname'] if 'peers_hostname' in request else ""
        file_name = request['file_name'] if 'file_name' in request else ""
        file_size = request['file_size'] if 'file_size' in request else ""
        piece_hash = request['piece_hash'] if 'piece_hash' in request else ""
        piece_size = request['piece_size'] if 'piece_size' in request else ""
        piece_order = request['piece_order'] if 'piece_order' in request else ""

        match req_option:
            case "signup":
                signup(conn, request)
            case "download":
                num_order_in_file_str = ','.join(map(str, piece_order))
                piece_hash_str = ','.join(map(str, piece_hash))

                # Execute the query
                cursor.execute("""
                    SELECT * FROM peers 
                    WHERE file_names = %s 
                    AND piece_order NOT IN (%s) 
                    AND piece_hash NOT IN (%s)
                    ORDER BY piece_order ASC;
                """, (file_name, num_order_in_file_str, piece_hash_str))
                result = cursor.fetchall()
                if result:
                    metainfo = []
                    for ID, IP, port, hostname, file_name, file_size, piece_hash, piece_size, piece_order in result:
                        tmp = {
                            'ID': ID,
                            'IP': IP,
                            'port': port,
                            'hostname': hostname,
                            'file_name': file_name,
                            'file_size': file_size,
                            'piece_hash': piece_hash,
                            'piece_size': piece_size,
                            'piece_order': piece_order
                        }
                        metainfo.append(tmp)
                    conn.sendall(json.dumps({'metainfo': metainfo}).encode())
                else :
                    conn.sendall(json.dumps({'metainfo': []}).encode())
            case "publish":
                print("Case publish\n")
            case "close":
                print("Case close\n")
            case "logout_request":
                conn.sendall(json.dumps({'status': 'logout_accepted'}).encode())
            case "logout_confirm":
                if conn in living_conn:
                    living_conn.remove(conn)
                    print(f"[LOGOUT] {addr} has logged out.")
                    print("[CONNECTION] Living connection: ", len(living_conn))
                conn.close()
                break
            
def login(conn, addr):
    try:
        while True:
            login_info = conn.recv(4096).decode()
            if (not login_info):
                print("[LOGIN] Missing email/password")
                conn.sendall(json.dumps({'status': False}).encode())
                return False
            else :
                login_info = json.loads(login_info)
                email = login_info['email']
                password = login_info['password']
                cursor.execute("SELECT email FROM login WHERE email = %s AND password = %s;", (email, password))
                successfull = cursor.fetchall()
                if successfull:
                    for hostname in successfull: peer_info = {'status': True, 'hostname': hostname}
                    conn.sendall(json.dumps(peer_info).encode())
                    living_conn.append(conn)
                    # print(conn)
                    print("[CONNECTION] Living connection: ", len(living_conn))
                    return True
                else :
                    conn.sendall(json.dumps({'status': False}).encode())
                    return False
    except Exception as error:
        print("[ERROR] Function login error", error)
    finally:
        # erase info of this conn in table peers before close connection
        print("[LOGIN] Function login run ok")

def is_prime(num):
    if num < 2:
        return False
    for i in range(2, int(num ** 0.5) + 1):
        if num % i == 0:
            return False
    return True

def generate_large_prime(min_val=50):
    prime = random.randint(min_val, min_val * 2)
    while not is_prime(prime):
        prime = random.randint(min_val, min_val * 2)
    return prime
     
# Modulo inverse
def mod_inverse(e, phi):
    d, x1, x2, y1 = 0, 0, 1, 1
    temp_phi = phi
    while e > 0:
        temp1, temp2 = temp_phi // e, temp_phi - temp_phi // e * e
        temp_phi, e = e, temp2
        x, y = x2 - temp1 * x1, d - temp1 * y1
        x2, x1, d, y1 = x1, x, y1, y
    if temp_phi == 1:
        return d + phi
    return None

# create RSA key
def generate_keypair():
    p = generate_large_prime()
    q = generate_large_prime()  
    while q == p:               
        q = generate_large_prime()
    n = p * q
    phi = (p - 1) * (q - 1)
    e = random.randrange(2, phi)
    while mod_inverse(e, phi) is None:
        e = random.randrange(2, phi)
    d = mod_inverse(e, phi)
    return ((e, n), (d, n))

# Encode
def encodeRsa(data):
    _code = data['code']
    public_key = data['key']
    e, n = public_key
    _encode = [pow(ord(char), e, n) for char in _code]
    return _encode

# Decode
def decodeRsa(data):
    _encode = data['code']
    private_key = data['key']
    d, n = private_key
    _decode = ''.join(chr(pow(char, d, n)) for char in _encode)
    return _decode

def signup(conn, request):
    try:
        email_data = {
            'code': request['email'],
            'key': private_key
        }
        password_data = {
            'code': request['password'],
            'key': private_key
        }
        email = decodeRsa(email_data)
        password = decodeRsa(password_data)

        # Kiểm tra xem email đã tồn tại trong database chưa
        cursor.execute("SELECT * FROM login WHERE email = %s;", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.sendall(json.dumps({'status': False, 'message': 'Email already exists'}).encode())
        else:
            # Thêm người dùng mới vào database
            cursor.execute("INSERT INTO login (email, password) VALUES (%s, %s);",
                           (email, password))
            con.commit()
            conn.sendall(json.dumps({'status': True}).encode())
            print(f"[SIGNUP] New user created: {email}")
    except Exception as error:
        print("[ERROR] Function signup error:", error)
        conn.sendall(json.dumps({'status': False, 'message': 'Signup failed'}).encode())
    finally:
        print("[TEST] Function signup run ok")

def terminal():
    option = input()
    while option != "close":
        if option == "ping":
            ping()
        elif option == "view_peers":
            view_peers()
        option = input()
    os._exit(0)

def server_main():
    global public_key, private_key
    public_key, private_key = generate_keypair()
    print("[INFO] Public Key:", public_key)
    print("[INFO] Private Key:", private_key)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # IPv4 and TCP/IP
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Config: can reuse IP immediately after closed
    server_socket.bind((TRACKER_ADDRESS, TRACKER_PORT))
    server_socket.listen()
    print(f"[LISTENING] Server is listening on PORT = {TRACKER_PORT}")

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"[ACCEPT] Connected to clients throught {conn.getsockname()}")
            print(f"[ACCEPT] Client socket: {addr}")
            thread = threading.Thread(target=client_handler, args=(conn, addr))
            thread.start()
            print(f"[SERVER] Active connections: {threading.active_count() - 1}")
            thread.join()
            # print("[TEST] Finding bug")

    except Exception as error:
            print(error)
    finally:
        server_socket.close()
        cursor.close()

if __name__ == "__main__":
    server_thread = threading.Thread(target=server_main)
    terminal_thread = threading.Thread(target=terminal)
    terminal_thread.start()
    server_thread.start()
    terminal_thread.join()
    server_thread.join()