import os
import sys
import yaml
import logging
import zmq.auth
import shutil

from collections import ChainMap

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def load_certificate(path):
    try:
        public_key, secret_key = zmq.auth.load_certificate(path)
    except Exception as e:
        logging.error(f'Failed to load {path}: {e}')
        sys.exit(1)
    return public_key, secret_key


def load_config(path, role):
    root_dir = os.path.dirname(os.path.abspath(path))
    keys_dir = os.path.join(root_dir, 'certificates')
    default = {
        'heartbeat': {
            'liveness': 5,
            'interval': 10,
        },
        'bufsize': 65536,
        'server': {
            'addr': '127.0.0.1',
            'port': 7011
        },
        'services': [],
        'public_keys_dir': os.path.join(keys_dir, 'clients'),
        'server_public_key_path': os.path.join(keys_dir, 'server.key'),
        'server_secret_key_path': os.path.join(keys_dir, 'server.key_secret'),
        'client_secret_key_path': os.path.join(keys_dir, 'client.key_secret'),
    }

    try:
        with open (path) as f:
            data = yaml.load(f, Loader=Loader)
    except Exception as e:
        logging.error(f'Load configuration file {path} failed: {e}')
        sys.exit(1)
    else:
        config = ChainMap(data, default)

        if role == 'client':
            config['server_key'], _ = load_certificate(config['server_public_key_path'])
        config['public_key'], config['secret_key'] = load_certificate(config[role + '_secret_key_path'])

    return config


def show_config(path):
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')

    try:
        with open(path, 'r') as f:
            data = yaml.load(f, Loader=Loader)
            print(yaml.dump(data, Dumper=Dumper))
    except Exception as e:
        print(f'{e}')
        sys.exit(1)
    else:
        sys.exit(0)


def create_config(path):
    """create config file in path, if the file doesn't exist, copy from sample config"""
    config_dir = os.path.dirname(path)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    if not os.path.exists(path):
        config_sample = os.path.join(os.path.dirname(__file__), 'config.yaml')
        shutil.copy(config_sample, path)
