# Netbox Device Importer

Clone the repo or otherwise download the code to your machine and change into the directory.

1. Create new virtual environment
```python3 -m venv venv```
2. Activate virtual environment
```source venv/bin/activate```
3. Install modules and cli
```pip install --editable .```
4. Copy .env.default file to .env and populate values
5. Run executable to test connectivity to Netbox. It should start printing out a list of device names from Netbox. Hit ctrl+C to cancel.
```netbox-device-importer test-netbox```
6. Prepare CSV using sample.csv file.
7. Import devices
```netbox-device-importer import-csv --file sample.csv```

