import socket
import threading
import mysql.connector as mysql
import json
import os

TRACKER_PORT = 50000
TRACKER_ADDRESS = "127.0.0.1" #Random IP  :vvv

connection_to_db = mysql.connect(host="localhost", user="root", password="", database="computer_network")
cursor=connection_to_db.cursor()
# cursor.execute("Some query"")

living_conn = []

def view_peers():
    print("view_peers")

def ping():
    print("ping")

def response_publish(conn):
    conn.sendall(json.dumps({"status": True}).encode())
    
def client_handler(conn, addr):
    login(conn, addr)
    print("[LOGIN] Logined, listening...")
    while True:
        req = conn.recv(4096).decode()
        if not req:
            break
        
        # Determine request
        request = json.loads(req)
        req_option = request['option']
        ip = addr[0]
        port = request['port'] if 'port' in request else ""
        hostname = request['hostname'] if 'hostname' in request else ""
        file_name = request['file_name'] if 'file_name' in request else ""
        file_size = request['file_size'] if 'file_size' in request else ""
        piece_hash = request['piece_hash'] if 'piece_hash' in request else ""
        piece_size = request['piece_size'] if 'piece_size' in request else ""
        piece_order = request['piece_order'] if 'piece_order' in request else ""

        match req_option:
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
                print("[PUBLISH] Publish start successful")
                delete_query = """
                    DELETE FROM peers
                    WHERE hostname = %s AND file_name = %s AND piece_order = %s; 
                """
                cursor.execute(delete_query, (hostname, file_name, piece_order))
                connection_to_db.commit()
                insert_query = """
                    INSERT INTO peers (ip, port, hostname, file_name, file_size, piece_hash, piece_size, piece_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (ip, port, hostname, file_name, file_size, piece_hash, piece_size, piece_order))
                connection_to_db.commit()
                response_publish(conn)
                print(ip, port, hostname, file_name, file_size, piece_hash, piece_size, piece_order)
                print("[PUBLISH] Publish successful")

            case "close":
                print("Case close\n")
            
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
                    if conn not in living_conn:
                        living_conn.append(conn)
                    # print(conn)
                    print("[CONNECTION] Living connection: ", len(living_conn))
                    # cursor.execute("""
                    #     INSERT INTO peers (host, column1, column2, ...)
                    #     VALUES ('host_value', 'value1', 'value2', ...)
                    #     ON DUPLICATE KEY UPDATE host = host;
                    # """, (email, password))
                    return True
                else :
                    conn.sendall(json.dumps({'status': False}).encode())
                    return False
    except Exception as error:
        print("[ERROR] Function login error", error)
    finally:
        # erase info of this conn in table peers before close connection
        print("[LOGIN] Function login run ok")

def terminal():
    option = input()
    while option != "exit":
        if option == "ping":
            ping()
        elif option == "view_peers":
            view_peers()
        option = input()
    os._exit(0)

def server_main():
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