from setuptools import setup

setup(
    name='netbox-device-importer',
    version='0.1',
    py_modules=['netbox_device_importer'],
    install_requires=[
        'Click',
        'pynetbox',
        'rich',
        'python-dotenv',
        'requests'
    ],
    entry_points='''
        [console_scripts]
        netbox-device-importer=netbox_device_importer:cli
    ''',
)
