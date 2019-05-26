import os
import zmq.auth
import click


@click.command()
@click.option('-d', '--certificates-dir', default=os.path.join(os.path.dirname(__file__), 'certificates'))
@click.option('-r', '--role', type=click.Choice(['server', 'client']))
def main(certificates_dir, role):
    if not os.path.exists(certificates_dir):
        print(f'Create key dir {certificates_dir}')
        os.makedirs(certificates_dir)

    zmq.auth.create_certificates(certificates_dir, role)

    if role == 'server':
        public_keys_dir = os.path.join(certificates_dir, 'clients')
        if not os.path.exists(public_keys_dir):
            print(f'Create public keys dir {public_keys_dir}')
            os.makedirs(public_keys_dir)


if __name__ == '__main__':
    main()