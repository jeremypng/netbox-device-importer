import click
import dotenv
import csv
from rich import print
from dotenv import load_dotenv
load_dotenv()
import os
import pynetbox
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
NETBOX_HOST = os.getenv("NETBOX_HOST")
NETBOX_PORT = os.getenv("NETBOX_PORT")

nb = pynetbox.api(f"https://{NETBOX_HOST}:{NETBOX_PORT}",token=NETBOX_TOKEN)
nb_session = requests.session()
nb_session.verify=False
nb.http_session=nb_session

def check_create_manufacturer(mfg_name):
    mfg = nb.dcim.manufacturers.get(name=mfg_name)
    if mfg is None:
        mfg_slug = mfg_name.lower().replace(" ","-")
        mfg = nb.dcim.manufacturers.create(
            name=mfg_name,
            slug=mfg_slug
        )
        print(f"Created manufacturer {mfg.name}")
    return mfg

def check_create_device_type(mfg, dev_type_name):
    dev_type = nb.dcim.device_types.get(model=dev_type_name)
    if dev_type is None:
        dev_type_slug = dev_type_name.lower().replace(" ","-").replace(".","_")
        dev_type = nb.dcim.device_types.create(
            manufacturer=mfg.id,
            model=dev_type_name,
            slug=dev_type_slug,
            height=1
        )
        print(f"Created device type {dev_type.model}")
        dev_type_eth0 = nb.dcim.interface_templates.create(
            device_type=dev_type.id,
            name="Eth0",
            type="1000base-t"
        )
        print(f"Created device type interface {dev_type_eth0.name}")
    return dev_type

def assign_mac_ip(mac_address, vrf, ip_address, int_name, dev_name, nb_dev, tenant, override, ignore_ip=False):
    # Assign mac address to interface
    if len(mac_address) == 17:
        nb_dev_eth0 = nb.dcim.interfaces.get(device_id=nb_dev.id,name=int_name)
        nb_dev_eth0.mac_address = mac_address
        nb_dev_eth0.save()
        print(f"Assigned mac {nb_dev_eth0.mac_address} to device {nb_dev.name}")
    
    if ignore_ip = False:
        vrf = nb.ipam.vrfs.get(name=vrf)
        if vrf is None:
            print(f"VRF {vrf} must exist in Netbox")
            return

        # Check for existing IP Assignment
        ip_list = []
        ip_query = nb.ipam.ip_addresses.filter(device_id=nb_dev.id)
        for ip in ip_query:
            if ip.assigned_object.name == int_name:
                ip_list.append(ip)
        if len(ip_list)>0 and override == False:
            print(f"{len(ip_list)} IP Address(es) already exist for {dev_name} in Netbox")
            return
        elif len(ip_list)==1 and override == True:
            ip_list[0].delete()
            print(f"Overriding current IP with {ip_address} for {nb_dev.name}")
        
        # Check for dangling IP address
        unassigned_ip = nb.ipam.ip_addresses.get(address=ip_address,vrf_id=vrf.id)
        if unassigned_ip:
            unassigned_ip.assigned_object_id = nb_dev_eth0.id
            unassigned_ip.assigned_object_type = "dcim.interface"
            unassigned_ip.tenant = tenant.id
            unassigned_ip.save()
            print(f"Updated unassigned ip {unassigned_ip.address} to {nb_dev.name}")
        else:
            nb_dev_ip = nb.ipam.ip_addresses.create(
                address=ip_address,
                vrf=vrf.id,
                tenant=tenant.id,
                status="active",
                assigned_object_id=nb_dev_eth0.id,
                assigned_object_type="dcim.interface"
            )
            print(f"Created ip {nb_dev_ip.address} for {nb_dev.name}")

@click.command("import-csv")
@click.option("--file", required=True)
@click.option("--override/--no-override", required=True, default=False)
@click.option("--ignore-location/--no-ignore-location", required=False, default=False)
@click.option("--ignore-ip/--no-ignore-ip", required=False, default=False)
@click.option("--enable-wifi/--disable-wifi", required=False, default=False)
@click.option("--set-mask", required=False, default=None)
def import_csv(file, override, ignore_location, enable_wifi, set_mask, ignore_ip):
    with open(file, encoding='utf-8-sig') as csvfile:
        device_reader = csv.DictReader(csvfile, delimiter=",", dialect="excel")
        for device in device_reader:
            mfg = check_create_manufacturer(device["manufacturer"])
            dev_type = check_create_device_type(mfg, device["device_type"])
            site = nb.dcim.sites.get(name=device["site"])
            if site is None:
                print(f"Site {device['site']} must exist in Netbox")
                return
            if ignore_location == False:
                location = nb.dcim.locations.get(name=device["location"])
                if location is None:
                    print(f"Location {device['location']} must exist in Netbox")
                    return
            dev_role = nb.dcim.device_roles.get(name=device["device_role"])
            if dev_role is None:
                print(f"Device Role {device['device_role']} must exist in Netbox")
                return
            tenant = nb.tenancy.tenants.get(name=device["tenant"])
            if tenant is None:
                print(f"Tenant {device['tenant']} must exist in Netbox")
                return

            #Check for existing device
            nb_dev = nb.dcim.devices.get(name=device["device_name"])
            if nb_dev is None:
                if ignore_location == False:
                    nb_dev = nb.dcim.devices.create(
                        name=device["device_name"],
                        device_type=dev_type.id,
                        site=site.id,
                        location=location.id,
                        device_role=dev_role.id,
                        tenant=tenant.id,
                        serial=device["serial_number"]
                    )
                else:
                    nb_dev = nb.dcim.devices.create(
                        name=device["device_name"],
                        device_type=dev_type.id,
                        site=site.id,
                        device_role=dev_role.id,
                        tenant=tenant.id,
                        serial=device["serial_number"]
                    )
                print(f"Created device {nb_dev.name}")
            elif override == True:
                nb_dev.device_type=dev_type.id
                nb_dev.site=site.id
                nb_dev.location=location.id
                nb_dev.device_role=dev_role.id
                nb_dev.tenant=tenant.id
                nb_dev.serial=device["serial_number"]
                nb_dev.save()
                print(f"Overrode device {nb_dev.name}")
                
            # update IP with mask if needed
            if set_mask:
                ip_address = f"{device['ip_address']}/{set_mask}"
                if enable_wifi:
                    wifi_ip_address = f"{device['wifi_ip_address']}/{set_mask}"
            else:
                ip_address = device["ip_address"]
                if enable_wifi:
                    ip_address = device["wifi_ip_address"]
            
            
            # Assign Eth0 interface mac/ip
            assign_mac_ip(device["mac_address"],device["vrf"],ip_address,"Eth0",device["device_name"],nb_dev,tenant,override,ignore_ip)
            
            # Assign Wifi0 interface mac/ip if enabled
            if enable_wifi == True:
                assign_mac_ip(device["wifi_mac_address"],device["vrf"],wifi_ip_address,"Wifi0",device["device_name"],nb_dev,tenant,override)
   
@click.command("test-netbox")
def test_netbox():
    device_list = nb.dcim.devices.all()
    for device in device_list:
        print(device)

@click.group()
def cli():
    """A tool for interacting with Netbox and NS1 DDI"""
    pass

cli.add_command(test_netbox)
cli.add_command(import_csv)

if __name__ == "__main__":
    cli()