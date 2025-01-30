"""
Automated Migration from pfSense to Ubiquiti UXG

This script automates the migration of DHCP reservations and static DNS entries from a pfSense 
firewall to a Ubiquiti UXG gateway using the UniFi Controller API.

Features:
- Connects to pfSense via SSH and extracts the `config.xml` file.
- Parses DHCP reservations and static DNS entries from `config.xml`.
- Authenticates with the UniFi Controller API.
- Finds the LAN network ID for the target network.
- Migrates DHCP reservations to the UXG.
- Generates a `config.gateway.json` file for static DNS mappings.
- Uploads `config.gateway.json` to the UniFi Controller and restarts the service.

Prerequisites:
- The script requires SSH access to both the pfSense firewall and the UniFi Controller.
- The UniFi Controller must be accessible via API (adjust the URL and credentials accordingly).
- Ensure your user has sufficient permissions to modify UniFi settings.

Usage:
1. Update the script variables (IP addresses, credentials, API details).
2. Run the script in a Python 3 environment.
3. Check the UniFi Controller to verify DHCP reservations.
4. If using `config.gateway.json`, ensure it is uploaded and applied correctly.

Author: Mikael Bendiksen
Date: 2025-01-30
Version: Alpha
"""

import paramiko
import requests
import xml.etree.ElementTree as ET
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # Ignore SSL warnings

# pfSense & Unifi script variables
PFSENSE_IP = "192.168.1.1"
PFSENSE_USER = "admin"
PFSENSE_PASSWORD = "your-password"
REMOTE_PATH = "/cf/conf/config.xml"
LOCAL_PATH = "config.xml"

UNIFI_CONTROLLER = "https://your-unifi-controller:8443"
UNIFI_USERNAME = "your-username"
UNIFI_PASSWORD = "your-password"
UNIFI_LAN_NAME = "default"
UNIFI_CONTROLLER_IP = "192.168.1.2"
UNIFI_API_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
REMOTE_PATH = "/usr/lib/unifi/data/sites/default/config.gateway.json"

# UniFi API Session
session = requests.Session()

def fetch_pfsense_config():
    """Fetch config.xml from pfSense via SSH."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(PFSENSE_IP, username=PFSENSE_USER, password=PFSENSE_PASSWORD)

    sftp = client.open_sftp()
    sftp.get(REMOTE_PATH, LOCAL_PATH)
    sftp.close()
    client.close()
    print("[+] Downloaded config.xml successfully!")

def parse_pfsense_config():
    """Extract DHCP reservations and static DNS entries from config.xml."""
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

    dns_entries = []
    for host in root.findall(".//hosts/host"):
        dns_entry = {
            "hostname": host.find("host").text,
            "ip": host.find("ip").text
        }
        dns_entries.append(dns_entry)

    print(f"[+] Extracted {len(dhcp_reservations)} DHCP reservations and {len(dns_entries)} static DNS entries.")
    return dhcp_reservations, dns_entries

def unifi_login():
    """Authenticate with the UniFi Controller API."""
    headers = {
        'X-API-KEY': UNIFI_API_KEY,
        'Accept': 'application/json'
    }
    response = session.post(f"{UNIFI_CONTROLLER}/proxy/network/api/self/sites", headers=headers, verify=False)

    if response.status_code == 200:
        print("[+] UniFi API login successful!")
    else:
        print("[-] UniFi API login failed:", response.text)
        exit(1)

def get_network_id():
    """Retrieve the UniFi network ID for LAN."""
    headers = {
        'X-API-KEY': UNIFI_API_KEY,
        'Accept': 'application/json'
    }
    response = session.get(f"{UNIFI_CONTROLLER}/proxy/network/api/s/default/rest/networkconf", headers=headers, verify=False)
    networks_data = response.json()["data"]

    for net in networks_data:
        if net["name"].lower() == UNIFI_LAN_NAME:
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
        
        response = session.post(f"{UNIFI_CONTROLLER}/proxy/network/api/s/default/rest/user", json=payload, headers=headers, verify=False)
        if response.status_code == 200:
            print(f"[+] Added {reservation['mac']} -> {reservation['fixed_ip']} ({reservation['name']})")
        else:
            print(f"[-] Failed to add {reservation['mac']} -> {reservation['fixed_ip']}: {response.text}")

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

# === Main Execution ===
fetch_pfsense_config()
dhcp_reservations, dns_entries = parse_pfsense_config()
unifi_login()
network_id = get_network_id()
migrate_dhcp_reservations(network_id, dhcp_reservations)
#generate_dns_json(dns_entries) # NOT TESTED
#upload_config_gateway_json()   # NOT TESTED