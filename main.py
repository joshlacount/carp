import socket
import struct
import json
import sys

MCAST_GROUP = '224.1.1.1'
MCAST_PORT = 5007
MAP_JSON_PATH = 'map.json'
HOSTS_PATH = '/etc/hosts'
HOSTS_START_STR = '# CARP START\n'
HOSTS_END_STR = '# CARP END'

IS_SERVER = int(sys.argv[1])

if IS_SERVER:
    print("Starting as server")
    with open(MAP_JSON_PATH, 'r') as fp:
        try:
            map_ = json.load(fp)
        except json.JSONDecodeError as e:
            print(f'Error decoding {MAP_JSON_PATH} - {e.msg}')
            sys.exit(1)
else:
    print("Starting as client")

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
    if IS_SERVER:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((MCAST_GROUP, MCAST_PORT))
        mreq = struct.pack('4sl', socket.inet_aton(MCAST_GROUP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        while True:
            data, addr = sock.recvfrom(10240)
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                print('Error decoding socket data')
                continue
            if 'proto' in data and data['proto'] == 'carp':
                map_[data['hostname']] = addr[0]
                with open(HOSTS_PATH, 'r+') as fp:
                    hosts_str = fp.read()
                    fp.seek(0)
                    start = hosts_str.find(HOSTS_START_STR) + len(HOSTS_START_STR)
                    end = hosts_str.find(HOSTS_END_STR, start)
                    new_hosts_str = hosts_str[:start]
                    for hostname, ip in map_.items():
                        new_hosts_str += f'{ip} {hostname}\n'
                    new_hosts_str += hosts_str[end:]
                    fp.write(new_hosts_str)
                    fp.truncate()
                with open(MAP_JSON_PATH, 'w') as fp:
                    json.dump(map_, fp)
                print(f'Added: {hostname} - {addr[0]}')
                reply = {
                    'proto': 'carp',
                    'status': 0
                }
                sock.sendto(bytes(json.dumps(reply), 'utf-8'), addr)
    else:
        while True:
            print('Sending hostname')
            data = {
                'proto': 'carp',
                'hostname': socket.gethostname() + '.local'
            }
            sock.sendto(bytes(json.dumps(data), 'utf-8'), (MCAST_GROUP, MCAST_PORT))
            try:
                recv_data = sock.recv(10240)
            except socket.timeout:
                print('Receive timed out')
                continue
            try:
                recv_data = json.loads(recv_data)
            except json.JSONDecodeError:
                print('Error decoding reply')
            if 'proto' in recv_data and recv_data['proto'] == 'carp':
                if recv_data['status'] == 0:
                    print('Hostname successfully added')
                    break
                else:
                    print('Failed to add hostname')
