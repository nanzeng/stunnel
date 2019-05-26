from setuptools import setup, find_packages

setup(
    name='stunnel',
    version='0.1.3',
    packages=find_packages(),
    setup_requires=['setuptools_scm'],
    install_requires=['click', 'pyzmq', 'pyyaml'],
    entry_points={
        'console_scripts': [
            'stunnel_client = stunnel.stunnel_client:main',
            'stunnel_server = stunnel.stunnel_server:main',
            'create_certificates = stunnel.create_certificates:main',
        ],
    },

    author='Nan Zeng',
    author_email='zengnan@gmail.com',
    description='provide tunnel for firewalled servers',
)
