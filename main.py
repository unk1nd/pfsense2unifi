"""
Automated Migration from pfSense to Ubiquiti UXG

This script automates the migration of DHCP reservations and static DNS entries from a pfSense 
firewall to a Ubiquiti UXG gateway using the UniFi Controller API.

Features:
- Connects to pfSense via SSH and extracts the `config.xml` file.
- Parses DHCP reservations and static DNS entries from `config.xml`.
- Authenticates with the UniFi Controller API.
- Finds SiteName to be used in URL for UniFi Controller API.
- Finds the LAN network ID for the target network.
- Migrates DHCP reservations to the UXG.
- Generates a `config.gateway.json` file for static DNS mappings.
- Uploads `config.gateway.json` to the UniFi Controller and restarts the service.

Prerequisites:
- The script requires SSH access to both the pfSense firewall and the UniFi Controller.
- The UniFi Controller must be accessible via API (adjust the URL and credentials accordingly).
- Ensure your user has sufficient permissions to modify UniFi settings.

Usage:
1. Update the config.ini (IP addresses, credentials, API details).
2. Installed required packages from the requiredment.txt file
3. Run the script in a Python 3 environment.
4. Check the UniFi Controller to verify DHCP reservations.
5. If using `config.gateway.json`, ensure it is uploaded and applied correctly.

Author: Mikael Bendiksen
Date: 2025-01-30
Version: Beta
"""

import paramiko
import requests
import argparse
import xml.etree.ElementTree as ET
import json
import urllib3
import configparser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # Ignore SSL warnings
config = configparser.ConfigParser()
config.read("config.ini")

# pfSense & Unifi script variables from config
PFSENSE_IP = config["PFSENSE"]["PFSENSE_IP"]
PFSENSE_USER = config["PFSENSE"]["PFSENSE_USER"]
PFSENSE_PASSWORD = config["PFSENSE"]["PFSENSE_PASSWORD"]
REMOTE_PATH = config["PFSENSE"]["REMOTE_PATH"]
LOCAL_PATH = config["PFSENSE"]["LOCAL_PATH"]
UNIFI_CONTROLLER = config["UNIFI"]["UNIFI_CONTROLLER"]
UNIFI_USERNAME = config["UNIFI"]["UNIFI_USERNAME"]
UNIFI_PASSWORD = config["UNIFI"]["UNIFI_PASSWORD"]
UNIFI_LAN_NAME = config["UNIFI"]["UNIFI_LAN_NAME"]
UNIFI_CONTROLLER_IP = config["UNIFI"]["UNIFI_CONTROLLER_IP"]
UNIFI_API_KEY = config["UNIFI"]["UNIFI_API_KEY"]
UNIFI_REMOTE_PATH = config["UNIFI"]["UNIFI_REMOTE_PATH"]

SITE = None

# Program args
parser = argparse.ArgumentParser(description="Automated Migration from pfSense to Ubiquiti UXG.", epilog="Run at own risk as its still in Beta. Follow updates on https://github.com/unk1nd/pfsense2unifi")
parser.add_argument("-a", "--all", dest="all", action="store_true", help="Run both for pfsense and unifi")
parser.add_argument("-p", "--pfsenseOnly", dest="pfsense", action="store_true", help="Run only pfsense fetching")
parser.add_argument("-u", "--unifiOnly", dest="unifi", action="store_true", help="Run Unifi parsing and storing")
parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Show Verbose (DHCP leases and IPs)")
args = parser.parse_args()


# UniFi API Session
session = requests.Session()

def fetch_pfsense_config():
    """Fetch config.xml from pfSense via SSH."""
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(PFSENSE_IP, username=PFSENSE_USER, password=PFSENSE_PASSWORD, allow_agent=False, look_for_keys=False)

    sftp = client.open_sftp()
    sftp.get(REMOTE_PATH, LOCAL_PATH)
    sftp.close()
    client.close()
    print("[+] Downloaded config.xml successfully!")

def parse_pfsense_config():
    """Extract DHCP reservations and static DNS entries from config.xml."""
    print(LOCAL_PATH)
    tree = ET.parse(LOCAL_PATH)
    root = tree.getroot()

    dhcp_reservations = []
    for static_mapping in root.findall(".//dhcpd//staticmap"):
        reservation = {
            "mac": static_mapping.find("mac").text,
            "ip": static_mapping.find("ipaddr").text,
            "hostname": static_mapping.find("hostname").text if static_mapping.find("hostname") is not None else "Unknown"
        }
        dhcp_reservations.append(reservation)
        if args.verbose:
            print(f"Found Static Mapping: {reservation}")

    dns_entries = []
    for host in root.findall(".//unbound/hosts"):
        dns_entry = {
            "hostname": host.find("host").text,
            "ip": host.find("ip").text,
            "domain": host.find("domain").text
        }
        dns_entries.append(dns_entry)
        if args.verbose:
            print(f"Found DNS entry: {dns_entry}")

    print(f"[+] Extracted {len(dhcp_reservations)} DHCP reservations and {len(dns_entries)} static DNS entries.")
    return dhcp_reservations, dns_entries

def unifi_login():
    """Authenticate with the UniFi Controller API."""
    headers = {
        'X-API-KEY': UNIFI_API_KEY,
        'Accept': 'application/json'
    }
    response = session.get(f"{UNIFI_CONTROLLER}/proxy/network/api/self", headers=headers, verify=False)

    if response.status_code == 200:
        print("[+] UniFi API login successful!")
    else:
        print("[-] UniFi API login failed:", response.text)
        exit(1)

def get_site_name():
    """Retrieve the UniFi sitename for LAN."""
    headers = {
        'X-API-KEY': UNIFI_API_KEY,
        'Accept': 'application/json'
    }
    sitename = session.get(f"{UNIFI_CONTROLLER}/proxy/network/api/self/sites", headers = headers, verify = False, timeout = 1).json() 
    sitename = sitename["data"][0]["name"]
    print(f"[+] Using Site: {sitename}")
    global SITE
    SITE = sitename

def get_network_id():
    """Retrieve the UniFi network ID for LAN."""
    headers = {
        'X-API-KEY': UNIFI_API_KEY,
        'Accept': 'application/json'
    }

    response = session.get(f"{UNIFI_CONTROLLER}/proxy/network/api/s/{SITE}/rest/networkconf", headers=headers, verify=False)
    networks_data = response.json()["data"]

    for net in networks_data:
        if net["name"].lower() == UNIFI_LAN_NAME:
            if args.verbose:
                print(f"[+] Found LAN network ID: {net['_id']}")
            return net["_id"]

    print("[-] LAN network not found!")
    exit(1)

def migrate_dhcp_reservations(network_id, reservations):
    """Migrate DHCP reservations to UniFi UXG."""

    headers = {
        'X-API-KEY': UNIFI_API_KEY,
        'Accept': 'application/json'
    }

    for reservation in reservations:
        payload = {
            "mac": reservation["mac"],
            "fixed_ip": reservation["ip"],
            "name": reservation["hostname"],
            "site_id": network_id,
            "use_fixedip": True,
        }
        
        response = session.post(f"{UNIFI_CONTROLLER}/proxy/network/api/s/{SITE}/rest/user", json=payload, headers=headers, verify=False)
        if response.status_code == 200:
            print(f"[+] Added {reservation['mac']} -> {reservation['ip']} ({reservation['hostname']})")
        else:
            print(f"[-] Failed to add {reservation['mac']} -> {reservation['ip']}: {response.text}")

def generate_dns_json(dns_entries):
    """Generate a config.gateway.json file for static DNS entries (if applicable)."""
    dns_config = {
        "system": {
            "static-host-mapping": {
                "host-name": {}
            }
        }
    }
    
    for entry in dns_entries:
        dns_config["system"]["static-host-mapping"]["host-name"][entry["hostname"]] = {
            "inet": [entry["ip"]]
        }

    with open("config.gateway.json", "w") as f:
        json.dump(dns_config, f, indent=4)
    
    print("[+] Generated config.gateway.json for static DNS entries.")

def upload_config_gateway_json():
    """Upload config.gateway.json to the UniFi Controller and restart the service."""

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(UNIFI_CONTROLLER_IP, username=UNIFI_SSH_USER, password=UNIFI_SSH_PASSWORD)

    sftp = client.open_sftp()
    sftp.put("config.gateway.json", REMOTE_PATH)
    sftp.close()
    
    print("[+] Uploaded config.gateway.json successfully!")

    # Restart UniFi Service to apply changes
    stdin, stdout, stderr = client.exec_command("sudo systemctl restart unifi")
    print(stdout.read().decode())
    client.close()
    print("[+] Restarted UniFi Controller!")


def main():
    # === Main Execution ===
    if not any(vars(args).values()):
       print("[!] No arguments given!\n")
       parser.print_help()
       exit(1)  # Exit with an error code

    if args.verbose:
        print("[!] Verbose mode enabled.")

    if args.all:
        fetch_pfsense_config()
        dhcp_reservations, dns_entries = parse_pfsense_config()
        unifi_login()
        get_site_name()
        network_id = get_network_id()
        migrate_dhcp_reservations(network_id, dhcp_reservations)
        generate_dns_json(dns_entries)
        #upload_config_gateway_json()   # NOT TESTED

    if args.pfsense and args.all != True:
        fetch_pfsense_config()
        dhcp_reservations, dns_entries = parse_pfsense_config()

    if args.unifi and args.all != True:
        dhcp_reservations, dns_entries = parse_pfsense_config()
        unifi_login()
        get_site_name()
        network_id = get_network_id()
        migrate_dhcp_reservations(network_id, dhcp_reservations)
        generate_dns_json(dns_entries)
        #upload_config_gateway_json()   # NOT TESTED

if __name__ == "__main__":
    main()