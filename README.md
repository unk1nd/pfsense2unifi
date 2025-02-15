# Automate Script for Migrating from Pfsense to Unifi

THIS IS A WORK IN PROGRES AND NOT COMPLETED   

Phase: Active Development

## Description

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

## Python env

```bash
> python3 -m venv venv
> venv/bin/pip install -r requirements.txt
> venv/bin/python main.py -h
```

## Functions Status

Tested functions:
- Login API unifi
- Adding static ip for new device
- Getting correct network id
- pfsense parse

Not tested at all yet
- static DNS for unifi api


## Command line
```bash
> python3 main.py -h

usage: main.py [-h] [-a] [-p] [-u] [-v]

Automated Migration from pfSense to Ubiquiti UXG.

options:
  -h, --help         show this help message and exit
  -a, --all          Run both for pfsense and unifi
  -p, --pfsenseOnly  Run only pfsense fetching
  -u, --unifiOnly    Run Unifi parsing and storing
  -v, --verbose      Show Verbose (DHCP leases and IPs)

Run at own risk as its still in Beta. Follow updates on https://github.com/unk1nd/pfsense2unifi
```

## Runtime example

```bash
> python3 main.py -a -v

[!] Verbose mode enabled.
[+] Downloaded config.xml successfully!
   - Found Static Mapping: {'mac': 'bc:24:11:74:d7:62', 'ip': '192.168.1.143', 'hostname': 'ubuntu_desktop'}
   - Found DNS entry: {'hostname': 'testdns', 'ip': '1.3.3.7', 'domain': 'bendiksens.net'}
[+] Extracted 1 DHCP reservations and 1 static DNS entries.
[+] UniFi API login successful!
[+] Using Site: 1ssty66m
[+] Found LAN network ID: 5ffc1e2302976a17c9aXXXXxX
[+] Added bc:24:11:74:d7:62 -> 192.168.1.143 (ubuntu_desktop)
[+] Generated config.gateway.json for static DNS entries.
```

## Issues?

Please create a issue and ill take a look at it, even if you have any request for changes or features
