# STunnel
=========

## Overview
-----------
The intention of this project is to easily expose any server behind a
firewall to the Internet. The STunnel server runs on a public accessible
server. An STunnel client runs on a computer behind a firewall,
where all the services are located. The client will connect to both 
STunnel server and local services, and build an encrypted communication
channel between the STunnel server and local services. Access to the services
from the Internet is through the STunnel server.

## Requirements
---------------
* Python 3.7+

## Install
----------
```
$ python setup.py install
```

## Configuration
----------------

### Server
1. Create certificate
```
$ create_certificates -r server
```

2. Start the server
```
$ stunnel_server -p 7777
```

### Client
1. Create certificate
```
$ create_certificates -r client
```

2. Copy client public key to server
```
# on server machine
$ cd $HOME/.config/stunnel/certificates
$ mkdir clients
$ cp client.key clients
```

3. Copy server public key to client
```
# on client machine
$ cd $HOME/.config/stunnel/certificates
$ mkdir servers
$ cp server.key servers
```

4. Update client configuration file
```
# $HOME/.config/stunnel/config.yaml

servers:
    - name: local
      addr: localhost
      port: 7777
      key: server.key

services:
    - name: ssh
      addr: localhost
      port: 22
      bind_port: 2222
```

5. Start an encrypted tunnel
```
$ stunnel_client
```

6. Connect to bind_port on server
```
$ ssh server -p 2222
```
An ssh connection should have been established
