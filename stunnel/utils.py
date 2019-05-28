import os
import sys
import yaml
import logging
import zmq.auth

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def load_config(role, config_path):
    if not os.path.exists(config_path):
        create_default_config(role, config_path)

    try:
        with open (config_path) as f:
            config = yaml.load(f, Loader=Loader)
    except Exception as e:
        logging.error(f'Load configuration file {config_path} failed: {e}')
    else:
        logging.info(f'Load configuration file {config_path}')

    # load certificates
    if role == 'client':
        for server in config['servers']:
            server['public_key'], _ = load_certificate(os.path.join(config['server_keys_dir'], server['key']))

    config['public_key'], config['secret_key'] = load_certificate(config[role + '_secret_key_path'])

    return config


def create_default_config(role, config_path):
    """create config file and save to path"""
    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        logging.info(f'Create configuration dir {config_dir}')
        os.makedirs(config_dir)

    keys_dir = os.path.join(config_dir, 'certificates')
    server_keys_dir = os.path.join(keys_dir, 'servers')
    client_keys_dir = os.path.join(keys_dir, 'clients')

    config = {
        'heartbeat': {
            'liveness': 5,
            'interval': 10,
        },
        'bufsize': 65536,
        'servers': [],
        'services': [],
        'client_keys_dir': client_keys_dir,
        'server_keys_dir': server_keys_dir,
        'server_secret_key_path': os.path.join(keys_dir, 'server.key_secret'),
        'client_secret_key_path': os.path.join(keys_dir, 'client.key_secret'),
    }

    if not os.path.exists(config_path):
        try:
            with open(config_path, 'w') as f:
                f.write(yaml.dump(config, Dumper=Dumper))
        except Exception as e:
            logging.error(f'Failed to create default configuration file {config_path}: {e}')
            sys.exit(1)
        else:
            logging.info(f'Created default configuration file {config_path}')

    if role == 'server' and not os.path.exists(client_keys_dir):
        logging.info(f'Create {client_keys_dir}')
        os.makedirs(client_keys_dir)

    if role == 'client' and not os.path.exists(server_keys_dir):
        logging.info(f'Create {server_keys_dir}')
        os.makedirs(server_keys_dir)


def load_certificate(path):
    try:
        public_key, secret_key = zmq.auth.load_certificate(path)
    except Exception as e:
        logging.error(f'Failed to load {path}: {e}')
        return None, None
    else:
        logging.info(f'Load certificate {path}')
    return public_key, secret_key


def show_config(role, config_path):
    config = load_config(role, config_path)
    print(yaml.dump(config, Dumper=Dumper))
    sys.exit(0)