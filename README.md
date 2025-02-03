# Automate Script for Migrating from Pfsense to Unifi

THIS IS A WORK IN PROGRES AND NOT COMPLETED  
Phase: Active Development

## Functions Status

Tested functions:
- Login API unifi
- Adding static ip for new device
- Getting correct network id
- pfsense parse

Not tested at all yet
- static DNS for unifi api


## Runtime

```bash
> python3 main.py

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