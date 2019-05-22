from setuptools import setup, find_packages

setup(
    name='stunnel',
    version='0.1.0',
    packages=find_packages(),

    install_requires=['click', 'pyzmq'],

    entry_points={
        'console_scripts': [
            'stunnel_client = stunnel.stunnel_client:main',
            'stunnel_server = stunnel.stunnel_server:main',
        ],
    },

    author='Nan Zeng',
    author_email='zengnan@gmail.com',
    description='provide tunnel for firewalled servers',
)
