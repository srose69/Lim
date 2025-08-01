# process_block.py
import curses
import psutil
import os
import time
import re
import platform
import subprocess
import sys
from math import floor
from utils import addstr_clipped, draw_box, bytes_to_mb_f, addstr_colored_markup
import datetime
from pathlib import Path
import json

DEBUG_DOCKER = False
DEBUG_LOG_FILE = "/tmp/py_monitor_debug.log"


def debug_print(*args, **kwargs):
    if DEBUG_DOCKER:
        try:
            with open(DEBUG_LOG_FILE, "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} ")
                print(*args, file=f, **kwargs)
        except Exception as e:
            try:
                print(f"DEBUG LOG Error: {e}", file=sys.__stderr__)
            except:
                pass


PREV_STATE_FILE = f"/tmp/py_monitor_prev_rss.{os.getuid()}.tsv"
MEM_THRESHOLD_HIGH = 1000
MEM_THRESHOLD_MED = 300
MEM_THRESHOLD_LOW = 100
CPU_THRESHOLD_HIGH = 80.0
DOCKER_CACHE_FILE = Path.home() / ".config/lim/docker_cache.json"
DOCKER_CACHE_REFRESH_INTERVAL = 10
prev_rss_cache = {}
last_read_time = 0
container_id_to_name_cache = {}
last_cache_read_time = 0
PROCESS_NAME_MAP = {
    "apache2": "Apache2 HTTPD",
    "httpd": "HTTPD",
    "nginx": "Nginx",
    "lighttpd": "Lighttpd",
    "mysqld": "MySQL",
    "mariadbd": "MariaDB",
    "postgres": "PostgreSQL",
    "mongod": "MongoDB",
    "redis-server": "Redis Server",
    "redis-cli": "Redis CLI",
    "memcached": "Memcached",
    "php-fpm": "PHP-FPM Worker",
    "supervisord": "Supervisor",
    "systemd": "Systemd",
    "cron": "Cron Daemon",
    "crond": "Cron Daemon",
    "sshd": "SSH Daemon",
    "dockerd": "Docker Daemon",
    "containerd": "Containerd",
    "containerd-shim": "Cont. Shim",
    "docker-proxy": "Docker Proxy",
    "java": "Java Process",
    "node": "Node.js",
    "node.js": "Node.js",
    "npm": "NPM",
    "yarn": "Yarn",
    "python": "Python Script",
    "python3": "Python Script",
    "python.exe": "Python Script",
    "python3.exe": "Python Script",
    "php": "PHP Script",
    "php.exe": "PHP Script",
    "ruby": "Ruby Script",
    "ruby.exe": "Ruby Script",
    "bash": "Bash",
    "zsh": "Zsh",
    "sh": "Shell",
    "tmux": "Tmux",
    "screen": "Screen",
    "vim": "Vim",
    "nvim": "Neovim",
    "emacs": "Emacs",
    "git": "Git",
    "ssh": "SSH Client",
    "scp": "SCP",
    "rsync": "Rsync",
    "ftp": "FTP Client",
    "wget": "Wget",
    "curl": "Curl",
    "tail": "Tail",
    "less": "Less",
    "more": "More",
    "grep": "Grep",
    "sed": "Sed",
    "awk": "Awk",
    "top": "Top",
    "htop": "Htop",
    "iotop": "Iotop",
    "iftop": "Iftop",
    "nload": "Nload",
    "slurmctld": "Slurm Controller",
    "slurmd": "Slurm Daemon",
    "kube-apiserver": "K8s API Server",
    "kubelet": "K8s Kubelet",
    "kube-proxy": "K8s Proxy",
    "kube-scheduler": "K8s Scheduler",
    "etcd": "etcd Database",
    "docker": "Docker CLI",
    "docker-compose": "Docker Compose",
    "containerd-shim-runc-v2": "Cont. Shim",
    "gnome-shell": "GNOME Shell",
    "Xorg": "X Server",
    "Xwayland": "XWayland",
    "gdm3": "GNOME Display Manager",
    "kwin_x11": "KWin (X11)",
    "kwin_wayland": "KWin (Wayland)",
    "plasmashell": "Plasma Shell",
    "systemd-journald": "Journald",
    "systemd-udevd": "Udevd",
    "systemd-resolved": "Resolved",
    "NetworkManager": "Network Manager",
    "wpa_supplicant": "WPA Supplicant",
    "dbus-daemon": "D-Bus Daemon",
    "pulseaudio": "PulseAudio",
    "pipewire": "PipeWire",
    "avahi-daemon": "Avahi Daemon",
    "cupsd": "CUPS Daemon",
    "cups-browsed": "CUPS Browser",
    "bluetoothd": "Bluetooth Daemon",
    "colord": "Color Daemon",
    "accounts-daemon": "Accounts Daemon",
    "udisksd": "UDisks Daemon",
    "gvfsd": "GVFS Daemon",
    "mutter": "Mutter",
    "cinnamon": "Cinnamon",
    "mate-session": "MATE Session",
    "lxsession": "LXSession",
    "xfce4-session": "XFCE Session",
    "lightdm": "LightDM",
    "sddm": "SDDM",
    "i3": "i3 WM",
    "awesome": "Awesome WM",
    "xmonad": "XMonad WM",
    "waybar": "Waybar",
    "polybar": "Polybar",
    "conky": "Conky",
    "gnome-terminal": "GNOME Terminal",
    "konsole": "Konsole",
    "xterm": "XTerm",
    "alacritty": "Alacritty",
    "terminator": "Terminator",
    "firefox": "Firefox",
    "chrome": "Chrome",
    "chromium": "Chromium",
    "opera": "Opera",
    "safari": "Safari",
    "thunderbird": "Thunderbird",
    "evolution": "Evolution",
    "libreoffice": "LibreOffice",
    "soffice.bin": "LibreOffice",
    "code": "VS Code",
    "atom": "Atom",
    "subl": "Sublime Text",
    "gedit": "Gedit",
    "nano": "Nano",
    "pico": "Pico",
    "micro": "Micro",
    "joe": "Joe",
    "ex": "Ex",
    "ed": "Ed",
    "vi": "Vi",
    "cc1": "C Compiler",
    "gcc": "GNU Compiler",
    "g++": "GNU C++ Compiler",
    "clang": "Clang Compiler",
    "clang++": "Clang C++ Compiler",
    "as": "Assembler",
    "ld": "Linker",
    "make": "Make",
    "cmake": "CMake",
    "ant": "Ant",
    "mvn": "Maven",
    "gradle": "Gradle",
    "go": "Go",
    "rustc": "Rust Compiler",
    "cargo": "Cargo",
    "javac": "Java Compiler",
    "scala": "Scala Compiler",
    "kotlinc": "Kotlin Compiler",
    "swift": "Swift Compiler",
    "asm": "Assembler",
    "fasm": "Flat Assembler",
    "nasm": "Netwide Assembler",
    "yasm": "Yet Another Assembler",
    "ld.bfd": "BFD Linker",
    "ld.gold": "Gold Linker",
    "ar": "Archiver",
    "ranlib": "Ranlib",
    "objcopy": "Objcopy",
    "objdump": "Objdump",
    "readelf": "Readelf",
    "strip": "Strip",
    "nm": "Nm",
    "size": "Size",
    "strings": "Strings",
    "c++filt": "C++filt",
    "addr2line": "Addr2line",
    "dwp": "Dwp",
    "gdb": "GDB",
    "lldb": "LLDB",
    "perf": "Perf",
    "valgrind": "Valgrind",
    "strace": "Strace",
    "ltrace": "Ltrace",
    "tcpdump": "Tcpdump",
    "wireshark": "Wireshark",
    "tshark": "Tshark",
    "ngrep": "Ngrep",
    "hping3": "Hping3",
    "nmap": "Nmap",
    "netcat": "Netcat",
    "nc": "Netcat",
    "socat": "Socat",
    "ss": "Ss",
    "ip": "Ip",
    "route": "Route",
    "ifconfig": "Ifconfig",
    "iwconfig": "Iwconfig",
    "iw": "Iw",
    "ping": "Ping",
    "traceroute": "Traceroute",
    "mtr": "MTR",
    "arp": "Arp",
    "bridge": "Bridge",
    "vconfig": "Vconfig",
    "ethtool": "Ethtool",
    "iproute2": "Iproute2",
    "quagga": "Quagga",
    "bird": "BIRD",
    "openbgpd": "OpenBGPD",
    "isc-dhcpd": "DHCP Server",
    "isc-dhcp-server": "DHCP Server",
    "isc-dhcp-client": "DHCP Client",
    "bind": "BIND",
    "named": "BIND",
    "unbound": "Unbound",
    "powerdns": "PowerDNS",
    "postfix": "Postfix",
    "sendmail": "Sendmail",
    "exim4": "Exim4",
    "qmail": "Qmail",
    "dovecot": "Dovecot",
    "courier-imap": "Courier IMAP",
    "cyrus-imapd": "Cyrus IMAPD",
    "apache2-prefork": "Apache2 Prefork",
    "apache2-worker": "Apache2 Worker",
    "apache2-event": "Apache2 Event",
    "uwsgi": "uWSGI",
    "gunicorn": "Gunicorn",
    "waitress-serve": "Waitress",
    "passenger": "Passenger",
    "thin": "Thin",
    "unicorn": "Unicorn",
    "puma": "Puma",
    "sidekiq": "Sidekiq",
    "celery": "Celery",
    "rqworker": "RQ Worker",
    "beanstalkd": "Beanstalkd",
    "gearman": "Gearman",
    "zeromq": "ZeroMQ",
    "rabbitmq-server": "RabbitMQ",
    "activemq": "ActiveMQ",
    "kafka": "Kafka",
    "zookeeper": "ZooKeeper",
    "consul": "Consul",
    "vault": "Vault",
    "cockroach": "CockroachDB",
    "cockroachdb": "CockroachDB",
    "tidb-server": "TiDB Server",
    "tikv-server": "TiKV Server",
    "mysql": "MySQL Server",
    "mariadb": "MariaDB Server",
    "percona-server": "Percona Server",
    "postgresql": "PostgreSQL Server",
    "mongodb": "MongoDB Server",
    "rethinkdb": "RethinkDB Server",
    "couchdb": "CouchDB Server",
    "arangod": "ArangoDB Server",
    "cassandra": "Cassandra Server",
    "redis": "Redis Server",
    "memcached": "Memcached Server",
    "influxd": "InfluxDB Server",
    "influxdb": "InfluxDB Server",
    "clickhouse-server": "ClickHouse Server",
    "elasticsearch": "Elasticsearch Server",
    "kibana": "Kibana",
    "logstash": "Logstash",
    "graylog": "Graylog Server",
    "prometheus": "Prometheus Server",
    "grafana-server": "Grafana Server",
    "grafana": "Grafana",
    "loki": "Loki",
    "jaeger-collector": "Jaeger Collector",
    "jaeger-agent": "Jaeger Agent",
    "fluentd": "Fluentd",
    "fluentbit": "Fluent Bit",
    "rsyslog": "Rsyslog Server",
    "syslog-ng": "Syslog-ng Server",
    "journald": "Journald Server",
    "auditd": "Auditd Server",
    "snmpd": "SNMP Daemon",
    "snmptrapd": "SNMP Trap Daemon",
    "chronyd": "Chrony Daemon",
    "ntpd": "NTP Daemon",
    "fail2ban-server": "Fail2Ban Server",
    "firewalld": "Firewalld Daemon",
    "ufw": "UFW Daemon",
    "iptables": "Iptables",
    "nftables": "Nftables",
    "apparmor": "AppArmor",
    "selinux": "SELinux",
    "clamav": "ClamAV Daemon",
    "freshclam": "ClamAV Updater",
    "spamassassin": "SpamAssassin",
    "opendkim": "OpenDKIM",
    "opendmarc": "OpenDMARC",
    "squid": "Squid Proxy",
    "haproxy": "HAProxy",
    "traefik": "Traefik",
    "caddy": "Caddy Server",
    "nginx-ingress": "Nginx Ingress",
    "envoy": "Envoy Proxy",
    "consul-template": "Consul Template",
    "nomad": "Nomad",
    "vault-agent": "Vault Agent",
    "etcdctl": "etcdctl",
    "kubectl": "Kubectl",
    "helm": "Helm",
    "terraform": "Terraform",
    "ansible-playbook": "Ansible Playbook",
    "ansible": "Ansible",
    "salt-master": "Salt Master",
    "salt-minion": "Salt Minion",
    "puppet-master": "Puppet Master",
    "puppet-agent": "Puppet Agent",
    "chef-client": "Chef Client",
    "chef-solo": "Chef Solo",
    "vagrant": "Vagrant",
    "virtualbox": "VirtualBox",
    "qemu-system-x86_64": "QEMU System",
    "kvm": "KVM System",
    "vmware-vmx": "VMware VM",
    "steam": "Steam",
    "lutris": "Lutris",
    "obs": "OBS Studio",
    "blender": "Blender",
    "gimp": "GIMP",
    "inkscape": "Inkscape",
    "audacity": "Audacity",
    "vlc": "VLC Media Player",
    "mpv": "MPV Player",
    "mplayer": "MPlayer",
    "transmission-gtk": "Transmission",
    "qbittorrent": "qBittorrent",
    "deluge": "Deluge",
    "filezilla": "FileZilla",
    "thunderbird": "Thunderbird Mail",
    "evolution": "Evolution Mail",
    "libreoffice-writer": "LibreOffice Writer",
    "libreoffice-calc": "LibreOffice Calc",
    "libreoffice-impress": "LibreOffice Impress",
    "libreoffice-draw": "LibreOffice Draw",
    "libreoffice-base": "LibreOffice Base",
    "libreoffice-math": "LibreOffice Math",
    "code": "VS Code",
    "atom": "Atom Editor",
    "subl": "Sublime Text",
    "gedit": "Gedit Editor",
    "nano": "Nano Editor",
    "pico": "Pico Editor",
    "micro": "Micro Editor",
    "emacs": "Emacs Editor",
    "vim": "Vim Editor",
    "nvim": "Neovim Editor",
    "joe": "Joe Editor",
    "xed": "Xed Editor",
    "mousepad": "Mousepad Editor",
    "leafpad": "Leafpad Editor",
    "geany": "Geany Editor",
    "kate": "Kate Editor",
    "notepadqq": "Notepadqq Editor",
    "pluma": "Pluma Editor",
    "scratch-text-editor": "Scratch Editor",
    "textedit": "TextEdit",
    "wordpad": "WordPad",
    "write": "Write",
    "abiword": "AbiWord",
    "openoffice.org-writer": "OpenOffice Writer",
    "openoffice.org-calc": "OpenOffice Calc",
    "openoffice.org-impress": "OpenOffice Impress",
    "openoffice.org-draw": "OpenOffice Draw",
    "openoffice.org-base": "OpenOffice Base",
    "openoffice.org-math": "OpenOffice Math",
    "soffice": "StarOffice",
    "soffice.bin": "StarOffice",
    "soffice.writer": "StarOffice Writer",
    "soffice.calc": "StarOffice Calc",
    "soffice.impress": "StarOffice Impress",
    "soffice.draw": "StarOffice Draw",
    "soffice.base": "StarOffice Base",
    "soffice.math": "StarOffice Math",
    "msoffice": "Microsoft Office",
    "excel": "Microsoft Excel",
    "powerpnt": "Microsoft PowerPoint",
    "winword": "Microsoft Word",
    "outlook": "Microsoft Outlook",
    "access": "Microsoft Access",
    "onenote": "Microsoft OneNote",
    "visio": "Microsoft Visio",
    "project": "Microsoft Project",
    "publisher": "Microsoft Publisher",
    "frontpg": "Microsoft FrontPage",
    "infopath": "Microsoft InfoPath",
    "lync": "Microsoft Lync",
    "skype": "Microsoft Skype",
    "teams": "Microsoft Teams",
    "zoom": "Zoom",
    "slack": "Slack",
    "discord": "Discord",
    "telegram-desktop": "Telegram",
    "signal-desktop": "Signal",
    "whatsapp-desktop": "WhatsApp",
    "skypeforlinux": "Skype for Linux",
    "google-chrome": "Google Chrome",
    "google-chrome-stable": "Google Chrome",
    "google-chrome-beta": "Google Chrome Beta",
    "google-chrome-unstable": "Google Chrome Unstable",
    "chromium-browser": "Chromium Browser",
    "chromium-browser-stable": "Chromium Browser",
    "chromium-browser-beta": "Chromium Browser Beta",
    "chromium-browser-unstable": "Chromium Browser Unstable",
    "firefox-esr": "Firefox ESR",
    "firefox-developer-edition": "Firefox Developer",
    "firefox-nightly": "Firefox Nightly",
    "opera-stable": "Opera Browser",
    "opera-beta": "Opera Beta",
    "opera-developer": "Opera Developer",
    "safari": "Safari Browser",
    "epiphany": "Epiphany Browser",
    "midori": "Midori Browser",
    "rekonq": "Rekonq Browser",
    "konqueror": "Konqueror Browser",
    "lynx": "Lynx Browser",
    "w3m": "W3M Browser",
    "links": "Links Browser",
    "elinks": "ELinks Browser",
    "dillo": "Dillo Browser",
    "netsurf": "NetSurf Browser",
    "seamonkey": "SeaMonkey Browser",
    "pale moon": "Pale Moon Browser",
    "waterfox": "Waterfox Browser",
    "iceweasel": "Iceweasel Browser",
    "iceape": "Iceape Browser",
    "thunderbird": "Thunderbird Email",
    "thunderbird-bin": "Thunderbird Email",
    "evolution": "Evolution Email",
    "evolution-alarm-notify": "Evolution Alarm",
    "geary": "Geary Email",
    "sylpheed": "Sylpheed Email",
    "claws-mail": "Claws Mail",
    "alpine": "Alpine Email",
    "mutt": "Mutt Email",
    "mail": "Mail Utility",
    "mailx": "Mailx Utility",
    "sendmail": "Sendmail Server",
    "postfix": "Postfix Server",
    "exim4": "Exim4 Server",
    "qmail": "Qmail Server",
    "dovecot": "Dovecot Server",
    "courier-imap": "Courier IMAP Server",
    "cyrus-imapd": "Cyrus IMAPD Server",
    "fetchmail": "Fetchmail Utility",
    "procmail": "Procmail Utility",
    "spamassassin": "SpamAssassin Utility",
    "bogofilter": "Bogofilter Utility",
    "amavisd-new": "Amavisd-new Utility",
    "clamav": "ClamAV Utility",
    "sa-learn": "SpamAssassin Learn",
    "sa-compile": "SpamAssassin Compile",
    "dkimproxy": "DKIM Proxy",
    "opendkim": "OpenDKIM Utility",
    "opendmarc": "OpenDMARC Utility",
    "squid": "Squid Proxy",
    "haproxy": "HAProxy",
    "traefik": "Traefik",
    "caddy": "Caddy Server",
    "nginx-ingress": "Nginx Ingress",
    "envoy": "Envoy Proxy",
    "consul-template": "Consul Template",
    "nomad": "Nomad",
    "vault-agent": "Vault Agent",
    "etcdctl": "etcdctl",
    "kubectl": "Kubectl",
    "helm": "Helm",
    "terraform": "Terraform",
    "ansible-playbook": "Ansible Playbook",
    "ansible": "Ansible",
    "salt-master": "Salt Master",
    "salt-minion": "Salt Minion",
    "puppet-master": "Puppet Master",
    "puppet-agent": "Puppet Agent",
    "chef-client": "Chef Client",
    "chef-solo": "Chef Solo",
    "vagrant": "Vagrant",
    "virtualbox": "VirtualBox",
    "qemu-system-x86_64": "QEMU System",
    "kvm": "KVM System",
    "vmware-vmx": "VMware VM",
    "steam": "Steam",
    "lutris": "Lutris",
    "obs": "OBS Studio",
    "blender": "Blender",
    "gimp": "GIMP",
    "inkscape": "Inkscape",
    "audacity": "Audacity",
    "vlc": "VLC Media Player",
    "mpv": "MPV Player",
    "mplayer": "MPlayer",
    "transmission-gtk": "Transmission",
    "qbittorrent": "qBittorrent",
    "deluge": "Deluge",
    "filezilla": "FileZilla",
    "thunderbird": "Thunderbird Mail",
    "evolution": "Evolution Mail",
    "libreoffice-writer": "LibreOffice Writer",
    "libreoffice-calc": "LibreOffice Calc",
    "libreoffice-impress": "LibreOffice Impress",
    "libreoffice-draw": "LibreOffice Draw",
    "libreoffice-base": "LibreOffice Base",
    "libreoffice-math": "LibreOffice Math",
    "code": "VS Code",
    "atom": "Atom Editor",
    "subl": "Sublime Text",
    "gedit": "Gedit Editor",
    "nano": "Nano Editor",
    "pico": "Pico Editor",
    "micro": "Micro Editor",
    "emacs": "Emacs Editor",
    "vim": "Vim Editor",
    "nvim": "Neovim Editor",
    "joe": "Joe Editor",
    "xed": "Xed Editor",
    "mousepad": "Mousepad Editor",
    "leafpad": "Leafpad Editor",
    "geany": "Geany Editor",
    "kate": "Kate Editor",
    "notepadqq": "Notepadqq Editor",
    "pluma": "Pluma Editor",
    "scratch-text-editor": "Scratch Editor",
    "textedit": "TextEdit",
    "wordpad": "WordPad",
    "write": "Write",
    "abiword": "AbiWord",
    "openoffice.org-writer": "OpenOffice Writer",
    "openoffice.org-calc": "OpenOffice Calc",
    "openoffice.org-impress": "OpenOffice Impress",
    "openoffice.org-draw": "OpenOffice Draw",
    "openoffice.org-base": "OpenOffice Base",
    "openoffice.org-math": "OpenOffice Math",
    "soffice": "StarOffice",
    "soffice.bin": "StarOffice",
    "soffice.writer": "StarOffice Writer",
    "soffice.calc": "StarOffice Calc",
    "soffice.impress": "StarOffice Impress",
    "soffice.draw": "StarOffice Draw",
    "soffice.base": "StarOffice Base",
    "soffice.math": "StarOffice Math",
    "msoffice": "Microsoft Office",
    "excel": "Microsoft Excel",
    "powerpnt": "Microsoft PowerPoint",
    "winword": "Microsoft Word",
    "outlook": "Microsoft Outlook",
    "access": "Microsoft Access",
    "onenote": "Microsoft OneNote",
    "visio": "Microsoft Visio",
    "project": "Microsoft Project",
    "publisher": "Microsoft Publisher",
    "frontpg": "Microsoft FrontPage",
    "infopath": "Microsoft InfoPath",
    "lync": "Microsoft Lync",
    "skype": "Microsoft Skype",
    "teams": "Microsoft Teams",
    "zoom": "Zoom",
    "slack": "Slack",
    "discord": "Discord",
    "telegram-desktop": "Telegram",
    "signal-desktop": "Signal",
    "whatsapp-desktop": "WhatsApp",
    "skypeforlinux": "Skype for Linux",
    "google-chrome": "Google Chrome",
    "google-chrome-stable": "Google Chrome",
    "google-chrome-beta": "Google Chrome Beta",
    "google-chrome-unstable": "Google Chrome Unstable",
    "chromium-browser": "Chromium Browser",
    "chromium-browser-stable": "Chromium Browser",
    "chromium-browser-beta": "Chromium Browser Beta",
    "chromium-browser-unstable": "Chromium Browser Unstable",
    "firefox-esr": "Firefox ESR",
    "firefox-developer-edition": "Firefox Developer",
    "firefox-nightly": "Firefox Nightly",
    "opera-stable": "Opera Browser",
    "opera-beta": "Opera Beta",
    "opera-developer": "Opera Developer",
    "safari": "Safari Browser",
    "epiphany": "Epiphany Browser",
    "midori": "Midori Browser",
    "rekonq": "Rekonq Browser",
    "konqueror": "Konqueror Browser",
    "lynx": "Lynx Browser",
    "w3m": "W3M Browser",
    "links": "Links Browser",
    "elinks": "ELinks Browser",
    "dillo": "Dillo Browser",
    "netsurf": "NetSurf Browser",
    "seamonkey": "SeaMonkey Browser",
    "pale moon": "Pale Moon Browser",
    "waterfox": "Waterfox Browser",
    "iceweasel": "Iceweasel Browser",
    "iceape": "Iceape Browser",
    "thunderbird": "Thunderbird Email",
    "thunderbird-bin": "Thunderbird Email",
    "evolution": "Evolution Email",
    "evolution-alarm-notify": "Evolution Alarm",
    "geary": "Geary Email",
    "sylpheed": "Sylpheed Email",
    "claws-mail": "Claws Mail",
    "alpine": "Alpine Email",
    "mutt": "Mutt Email",
    "mail": "Mail Utility",
    "mailx": "Mailx Utility",
    "sendmail": "Sendmail Server",
    "postfix": "Postfix Server",
    "exim4": "Exim4 Server",
    "qmail": "Qmail Server",
    "dovecot": "Dovecot Server",
    "courier-imap": "Courier IMAP Server",
    "cyrus-imapd": "Cyrus IMAPD Server",
    "fetchmail": "Fetchmail Utility",
    "procmail": "Procmail Utility",
    "spamassassin": "SpamAssassin Utility",
    "bogofilter": "Bogofilter Utility",
    "amavisd-new": "Amavisd-new Utility",
    "clamav": "ClamAV Utility",
    "sa-learn": "SpamAssassin Learn",
    "sa-compile": "SpamAssassin Compile",
    "dkimproxy": "DKIM Proxy",
    "opendkim": "OpenDKIM Utility",
    "opendmarc": "OpenDMARC Utility",
    "squid": "Squid Proxy",
    "haproxy": "HAProxy",
    "traefik": "Traefik",
    "caddy": "Caddy Server",
    "nginx-ingress": "Nginx Ingress",
    "envoy": "Envoy Proxy",
    "consul-template": "Consul Template",
    "nomad": "Nomad",
    "vault-agent": "Vault Agent",
    "etcdctl": "etcdctl",
    "kubectl": "Kubectl",
    "helm": "Helm",
    "terraform": "Terraform",
    "ansible-playbook": "Ansible Playbook",
    "ansible": "Ansible",
    "salt-master": "Salt Master",
    "salt-minion": "Salt Minion",
    "puppet-master": "Puppet Master",
    "puppet-agent": "Puppet Agent",
    "chef-client": "Chef Client",
    "chef-solo": "Chef Solo",
    "vagrant": "Vagrant",
    "virtualbox": "VirtualBox",
    "qemu-system-x86_64": "QEMU System",
    "kvm": "KVM System",
    "vmware-vmx": "VMware VM",
    "steam": "Steam",
    "lutris": "Lutris",
    "obs": "OBS Studio",
    "blender": "Blender",
    "gimp": "GIMP",
    "inkscape": "Inkscape",
    "audacity": "Audacity",
    "vlc": "VLC Media Player",
    "mpv": "MPV Player",
    "mplayer": "MPlayer",
    "transmission-gtk": "Transmission",
    "qbittorrent": "qBittorrent",
    "deluge": "Deluge",
    "filezilla": "FileZilla",
    "thunderbird": "Thunderbird Mail",
    "evolution": "Evolution Mail",
    "libreoffice-writer": "LibreOffice Writer",
    "libreoffice-calc": "LibreOffice Calc",
    "libreoffice-impress": "LibreOffice Impress",
    "libreoffice-draw": "LibreOffice Draw",
    "libreoffice-base": "LibreOffice Base",
    "libreoffice-math": "LibreOffice Math",
    "code": "VS Code",
    "atom": "Atom Editor",
    "subl": "Sublime Text",
    "gedit": "Gedit Editor",
    "nano": "Nano Editor",
    "pico": "Pico Editor",
    "micro": "Micro Editor",
    "emacs": "Emacs Editor",
    "vim": "Vim Editor",
    "nvim": "Neovim Editor",
    "joe": "Joe Editor",
    "xed": "Xed Editor",
    "mousepad": "Mousepad Editor",
    "leafpad": "Leafpad Editor",
    "geany": "Geany Editor",
    "kate": "Kate Editor",
    "notepadqq": "Notepadqq Editor",
    "pluma": "Pluma Editor",
    "scratch-text-editor": "Scratch Editor",
    "textedit": "TextEdit",
    "wordpad": "WordPad",
    "write": "Write",
    "abiword": "AbiWord",
    "openoffice.org-writer": "OpenOffice Writer",
    "openoffice.org-calc": "OpenOffice Calc",
    "openoffice.org-impress": "OpenOffice Impress",
    "openoffice.org-draw": "OpenOffice Draw",
    "openoffice.org-base": "OpenOffice Base",
    "openoffice.org-math": "OpenOffice Math",
    "soffice": "StarOffice",
    "soffice.bin": "StarOffice",
    "soffice.writer": "StarOffice Writer",
    "soffice.calc": "StarOffice Calc",
    "soffice.impress": "StarOffice Impress",
    "soffice.draw": "StarOffice Draw",
    "soffice.base": "StarOffice Base",
    "soffice.math": "StarOffice Math",
    "msoffice": "Microsoft Office",
    "excel": "Microsoft Excel",
    "powerpnt": "Microsoft PowerPoint",
    "winword": "Microsoft Word",
    "outlook": "Microsoft Outlook",
    "access": "Microsoft Access",
    "onenote": "Microsoft OneNote",
    "visio": "Microsoft Visio",
    "project": "Microsoft Project",
    "publisher": "Microsoft Publisher",
    "frontpg": "Microsoft FrontPage",
    "infopath": "Microsoft InfoPath",
    "lync": "Microsoft Lync",
    "skype": "Microsoft Skype",
    "teams": "Microsoft Teams",
    "zoom": "Zoom",
    "slack": "Slack",
    "discord": "Discord",
    "telegram-desktop": "Telegram",
    "signal-desktop": "Signal",
    "whatsapp-desktop": "WhatsApp",
}


def read_prev_rss_state():
    global prev_rss_cache, last_read_time
    now = time.time()
    if not prev_rss_cache or now - last_read_time > 5:
        prev_rss_cache = {}
        if os.path.exists(PREV_STATE_FILE):
            try:
                with open(PREV_STATE_FILE, "r") as f:
                    for line in f:
                        parts = line.strip().split("\t")
                        if len(parts) == 2:
                            prev_rss_cache[parts[0]] = parts[1]
                last_read_time = now
            except Exception:
                pass
    return prev_rss_cache


def save_current_rss_state(current_rss):
    try:
        temp_new_state = f"{PREV_STATE_FILE}.new"
        with open(temp_new_state, "w") as f:
            for pid, rss in current_rss.items():
                f.write(f"{str(pid)}\t{str(rss)}\n")
        os.replace(temp_new_state, PREV_STATE_FILE)
        os.chmod(PREV_STATE_FILE, 0o600)
    except Exception:
        pass


def get_container_id_from_cgroup(pid):
    if platform.system() != "Linux":
        return None
    try:
        pattern = re.compile(
            r"(?:docker-|/docker/|docker-|kubepods.*/pod[^/]+/)([0-9a-f]{64})"
        )
        cgroup_path = f"/proc/{pid}/cgroup"
        if not os.path.exists(cgroup_path):
            return None
        with open(cgroup_path, "r") as f:
            cgroup_content = f.read()
        match = pattern.search(cgroup_content)
        full_id = match.group(1) if match else None
        return full_id
    except Exception as e:
        debug_print(f"get_container_id_from_cgroup({pid}): ERROR: {e}")
        return None

def _refresh_docker_cache():
    global container_id_to_name_cache, last_cache_read_time
    now = time.time()
    if now - last_cache_read_time < DOCKER_CACHE_REFRESH_INTERVAL:
        return

    debug_print(f"Refreshing Docker cache from JSON: {DOCKER_CACHE_FILE}...")
    new_cache = {}
    
    try:
        if DOCKER_CACHE_FILE.is_file():
            with open(DOCKER_CACHE_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
            
            containers_data = data.get("containers", {})
            for container_info in containers_data.values():
                full_id = container_info.get("id")
                name = container_info.get("name")
                if full_id and name:
                    new_cache[full_id] = name
            
            container_id_to_name_cache = new_cache
            last_cache_read_time = now
            debug_print(f"  JSON Cache refreshed. New size: {len(container_id_to_name_cache)}")
        else:
            debug_print(f"  Cache file {DOCKER_CACHE_FILE} not found.")
            container_id_to_name_cache.clear()
            last_cache_read_time = now

    except (json.JSONDecodeError, OSError) as e:
        debug_print(f"  Cache refresh FAILED: {e}")
        container_id_to_name_cache.clear() 
        last_cache_read_time = now
    except Exception as e:
        debug_print(f"  Unexpected cache refresh FAILED: {e}")
        container_id_to_name_cache.clear()
        last_cache_read_time = now


def get_docker_info(pid):
    global container_id_to_name_cache
    container_id_full = get_container_id_from_cgroup(pid)
    if not container_id_full:
        return None
    needs_refresh = container_id_full not in container_id_to_name_cache
    if needs_refresh:
        debug_print(
            f"get_docker_info({pid}): ID {container_id_full[:12]}... not in cache. Refreshing."
        )
        _refresh_docker_cache()
    cached_name = container_id_to_name_cache.get(container_id_full)
    if cached_name:
        debug_print(f"get_docker_info({pid}): Found name in cache: '{cached_name}'")
        return cached_name
    else:
        short_id = container_id_full[:12]
        debug_print(
            f"get_docker_info({pid}): Name for ID {short_id}... NOT found. Returning short ID."
        )
        return short_id


def get_display_name(pinfo):
    name = pinfo.get("name")
    cmdline = pinfo.get("cmdline") or []
    display_name = name if name else "N/A"
    if name in PROCESS_NAME_MAP:
        display_name = PROCESS_NAME_MAP[name]
        if display_name == "Java Process":
            jar_name = None
            try:
                jar_idx = cmdline.index("-jar")
                if jar_idx + 1 < len(cmdline):
                    jar_name = os.path.basename(cmdline[jar_idx + 1])
            except (ValueError, IndexError):
                pass
            if jar_name:
                display_name = f"Java: {jar_name}"
        elif display_name == "Python Script" or (name and "python" in name.lower()):
            script_name = None
            for arg in cmdline[1:]:
                if arg.endswith(".py"):
                    script_name = os.path.basename(arg)
                    break
                elif not arg.startswith("-"):
                    script_name = os.path.basename(arg)
                    break
            if script_name:
                display_name = f"Py: {script_name}"
            elif name and name.lower() not in ["python", "python3"]:
                display_name = name
            else:
                display_name = "Python Interp."
        elif display_name == "PHP Script" or (
            name and "php" in name.lower() and "php-fpm" not in name
        ):
            script_name = None
            for arg in cmdline[1:]:
                if arg.endswith(".php"):
                    script_name = os.path.basename(arg)
                    break
                elif not arg.startswith("-"):
                    script_name = os.path.basename(arg)
                    break
            if script_name:
                display_name = f"PHP: {script_name}"
            else:
                display_name = "PHP Script"
    elif display_name == "N/A" and cmdline:
        try:
            display_name = os.path.basename(cmdline[0])
        except IndexError:
            display_name = "N/A"
    return display_name if display_name else "N/A"


def get_processes(sort_key):
    processes = []
    attrs = [
        "pid",
        "name",
        "username",
        "cpu_percent",
        "memory_info",
        "memory_percent",
        "cmdline",
    ]
    _refresh_docker_cache()
    for proc in psutil.process_iter(attrs=attrs, ad_value=None):
        try:
            pinfo = proc.info
            if (
                pinfo["pid"] is None
                or pinfo["name"] is None
                or pinfo["username"] is None
                or pinfo["memory_info"] is None
                or pinfo["name"] == "idle"
                or "kernel_task" in pinfo["name"]
            ):
                continue
            mem_info = pinfo.get("memory_info")
            pinfo["rss_mb"] = (
                bytes_to_mb_f(mem_info.rss)
                if mem_info and mem_info.rss is not None
                else 0.0
            )
            pinfo["vms_mb"] = (
                bytes_to_mb_f(mem_info.vms)
                if mem_info and mem_info.vms is not None
                else 0.0
            )
            pinfo["cpu_percent"] = pinfo.get("cpu_percent")
            if pinfo["cpu_percent"] is None:
                try:
                    pinfo["cpu_percent"] = proc.cpu_percent(interval=None) or 0.0
                except Exception:
                    pinfo["cpu_percent"] = 0.0
            if pinfo["cpu_percent"] is None:
                pinfo["cpu_percent"] = 0.0
            pinfo["memory_percent"] = pinfo.get("memory_percent") or 0.0
            if pinfo["memory_percent"] is None:
                pinfo["memory_percent"] = 0.0
            pinfo["display_name"] = get_display_name(pinfo)
            pinfo["docker_info"] = get_docker_info(pinfo["pid"])
            processes.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    sort_keys = {
        "cpu": "cpu_percent",
        "pid": "pid",
        "rss": "rss_mb",
        "vms": "vms_mb",
        "mem": "memory_percent",
        "name": "display_name",
    }
    sort_field = sort_keys.get(sort_key, "rss_mb")
    is_reversed = sort_key != "pid"

    def sort_key_func(process_info):
        value = process_info.get(sort_field)
        if sort_field == "display_name":
            return str(value).lower() if value is not None else ""
        else:
            if value is None:
                return 0
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0

    try:
        processes.sort(key=sort_key_func, reverse=is_reversed)
    except Exception as e:
        debug_print(f"Sort Error: {e}")
        pass
    return processes


def draw_process_block_content(
    win,
    key_attr,
    value_attr,
    cmd_attr,
    user_attrs,
    rss_color_map,
    cpu_high_attr,
    sort_key,
    mode="normal",
    selected_line=0,
    process_list=None,
    docker_attr=0,
    docker_container_attr=0,
    killer_attr=0,
    is_selecting=False,
):
    try:
        if not win:
            return 0
        h, w = win.getmaxyx()
        has_colors = curses.has_colors()
        if h < 3 or w < 10:
            return 0
        is_docker_mode = mode == "docker"
        is_killer_mode = mode == "killer"
        if is_docker_mode:
            current_value_attr = docker_attr
            current_key_attr = docker_attr | curses.A_BOLD
            current_cmd_attr = docker_attr
            base_container_attr = docker_container_attr
        elif is_killer_mode:
            current_value_attr = killer_attr
            current_key_attr = killer_attr | curses.A_BOLD
            current_cmd_attr = killer_attr
            base_container_attr = killer_attr | curses.A_DIM
        else:
            current_value_attr = value_attr
            current_key_attr = key_attr
            current_cmd_attr = cmd_attr
            base_container_attr = value_attr | curses.A_DIM
        current_user_attrs = {
            "root": current_value_attr | curses.A_BOLD,
            "normal": current_value_attr,
        }
        mode_str = f" ({mode.upper()})" if mode != "normal" else ""
        title_text = f"Processes{mode_str} (Sort: {sort_key.upper()})"
        title_attr = current_key_attr | curses.A_BOLD
        draw_box(win, title=title_text, title_attr=title_attr)
        help_hint_text = (
            "[<c3>h</>]elp [<c1>d</>]ock [<c4>k</>]ill [<c3>Tab</>]Sort [<c3>q</>]uit"
        )
        plain_hint_len = len(re.sub(r"</?\w*>", "", help_hint_text))
        hint_x = w - plain_hint_len - 3
        if hint_x > 1:
            hint_default_attr = curses.A_DIM
            hint_tag_map = {}
            if has_colors:
                hint_tag_map = {
                    "<c1>": curses.color_pair(1) | curses.A_BOLD,
                    "<c3>": curses.color_pair(3) | curses.A_BOLD,
                    "<c4>": curses.color_pair(4) | curses.A_BOLD,
                }
            else:
                hint_tag_map = {
                    "<c1>": curses.A_BOLD,
                    "<c3>": curses.A_BOLD,
                    "<c4>": curses.A_REVERSE,
                }
            addstr_colored_markup(
                win, 0, hint_x, help_hint_text, hint_default_attr, hint_tag_map
            )
        procs_drawn_count = 0
        processes_to_draw = (
            process_list if process_list is not None else get_processes(sort_key)
        )
        if is_docker_mode and process_list is None:
            processes_to_draw = [p for p in processes_to_draw if p.get("docker_info")]
        header_y = 1
        content_y_start = 2
        max_content_rows = h - 1 - content_y_start
        if max_content_rows <= 0:
            return 0
        header = ""
        proc_cmd_real_width = 0
        col_rss_real_width = 0
        name_w = 0
        col_container = 0
        col_pid = 7
        col_cpu = 6
        col_mem = 6
        col_rss = 9
        col_user = 10
        col_vms = 9
        spacing = 1
        col_container_norm = 22
        header_attr = current_key_attr | curses.A_BOLD
        if is_docker_mode:
            fixed_total_w = col_pid + col_cpu + col_mem + col_rss + (5 * spacing)
            remaining_w = max(0, w - 2 - fixed_total_w)
            if remaining_w < 18:
                name_w = max(1, floor(remaining_w * 0.4))
                col_container = max(1, remaining_w - name_w)
            else:
                name_w = max(8, floor(remaining_w * 0.4))
                col_container = max(10, remaining_w - name_w)
            current_total_w = (
                col_pid
                + name_w
                + col_container
                + col_cpu
                + col_mem
                + col_rss
                + (5 * spacing)
            )
            overshoot = current_total_w - (w - 2)
            if overshoot > 0:
                total_flexible = name_w + col_container
                if total_flexible > 0:
                    name_ratio = name_w / total_flexible
                    name_w = max(1, name_w - floor(overshoot * name_ratio))
                    col_container = max(
                        1, col_container - (overshoot - floor(overshoot * name_ratio))
                    )
            width_before_rss = (
                1
                + col_pid
                + spacing
                + name_w
                + spacing
                + col_container
                + spacing
                + col_cpu
                + spacing
                + col_mem
                + spacing
            )
            col_rss_real_width = max(1, w - 1 - width_before_rss)
            header = (
                f"{'PID':<{col_pid}}{' ' * spacing}{'NAME/INFO':<{name_w}}{' ' * spacing}"
                f"{'CONTAINER':<{col_container}}{' ' * spacing}{'%CPU':>{col_cpu}}{' ' * spacing}"
                f"{'%MEM':>{col_mem}}{' ' * spacing}{'RSS(MB)':<{col_rss_real_width}}"
            )
        else:
            fixed_width_before_last = (
                1
                + sum(
                    [
                        col_pid,
                        col_user,
                        col_cpu,
                        col_mem,
                        col_rss,
                        col_vms,
                        col_container_norm,
                    ]
                )
                + (6 * spacing)
            )
            proc_cmd_real_width = max(1, w - 1 - fixed_width_before_last)
            header = (
                f"{'PID':<{col_pid}}{' ' * spacing}{'USER':<{col_user}}{' ' * spacing}"
                f"{'%CPU':>{col_cpu}}{' ' * spacing}{'%MEM':>{col_mem}}{' ' * spacing}"
                f"{'RSS(MB)':>{col_rss}}{' ' * spacing}{'VMS(MB)':>{col_vms}}{' ' * spacing}"
                f"{'CONTAINER':<{col_container_norm}}{' ' * spacing}{'NAME/INFO':<{proc_cmd_real_width}}"
            )
        addstr_clipped(win, header_y, 1, header, header_attr)
        prev_rss = read_prev_rss_state()
        current_rss_to_save = {}
        for y in range(content_y_start, h - 1):
            win.move(y, 1)
            win.clrtoeol()
        for i, p in enumerate(processes_to_draw):
            line_y = content_y_start + i
            if line_y >= h - 1:
                break
            pid = p.get("pid", 0)
            pid_s = str(pid)
            cpu_perc = p.get("cpu_percent", 0.0)
            cpu_perc_s = f"{cpu_perc:.1f}"
            mem_perc = p.get("memory_percent", 0.0)
            mem_perc_s = f"{mem_perc:.1f}"
            rss_mb = p.get("rss_mb", 0.0)
            rss_mb_s = f"{rss_mb:.1f}"
            vms_mb = p.get("vms_mb", 0.0)
            vms_mb_s = f"{vms_mb:.1f}"
            display_name = p.get("display_name", "N/A")
            docker_info = p.get("docker_info", "") or ""
            user = p.get("username", "N/A")
            highlight_char = ""
            prev_rss_val_str = prev_rss.get(pid_s)
            if prev_rss_val_str is not None:
                if prev_rss_val_str != rss_mb_s:
                    try:
                        rss_f = float(rss_mb_s)
                        prev_rss_f = float(prev_rss_val_str)
                        if rss_f > prev_rss_f:
                            highlight_char = "+"
                        elif rss_f < prev_rss_f:
                            highlight_char = "-"
                        else:
                            highlight_char = "*"
                    except ValueError:
                        highlight_char = "*"
            else:
                highlight_char = "+"
            rss_display = f"{rss_mb_s}{highlight_char}"
            current_rss_to_save[pid_s] = rss_mb_s
            line_attr = current_value_attr
            line_cmd_attr = current_cmd_attr
            line_cpu_attr = line_attr
            if (
                cpu_perc > CPU_THRESHOLD_HIGH
                and not is_docker_mode
                and not is_killer_mode
            ):
                line_cpu_attr = cpu_high_attr
            line_rss_attr = line_attr | curses.A_BOLD
            if not is_docker_mode and not is_killer_mode:
                rss_color_key = (
                    "high"
                    if rss_mb > MEM_THRESHOLD_HIGH
                    else (
                        "med"
                        if rss_mb > MEM_THRESHOLD_MED
                        else ("low" if rss_mb > MEM_THRESHOLD_LOW else "default")
                    )
                )
                if has_colors:
                    rss_color_pair_index = rss_color_map.get(
                        rss_color_key, rss_color_map["default"]
                    )
                    line_rss_attr = (
                        curses.color_pair(rss_color_pair_index) | curses.A_BOLD
                    )
                else:
                    line_rss_attr = curses.A_BOLD
            line_user_attr = current_user_attrs.get(user, current_user_attrs["normal"])
            if user == "root":
                line_user_attr = current_user_attrs["root"]
            vms_attr = line_attr
            mem_perc_attr = line_attr
            line_container_attr_final = base_container_attr
            if is_docker_mode and docker_info:
                line_container_attr_final = docker_container_attr
            is_selected = i == selected_line and (is_selecting or is_killer_mode)
            if is_selected:
                reverse_attr = curses.A_REVERSE
                line_attr |= reverse_attr
                line_user_attr |= reverse_attr
                line_cmd_attr |= reverse_attr
                line_cpu_attr |= reverse_attr
                line_rss_attr |= reverse_attr
                vms_attr |= reverse_attr
                mem_perc_attr |= reverse_attr
                line_container_attr_final |= reverse_attr
            x = 1
            try:
                if is_docker_mode:
                    name_info_clipped = display_name[:name_w]
                    cont_name_clipped = docker_info[:col_container]
                    addstr_clipped(win, line_y, x, f"{pid_s:<{col_pid}}", line_attr)
                    x += col_pid + spacing
                    addstr_clipped(
                        win, line_y, x, f"{name_info_clipped:<{name_w}}", line_cmd_attr
                    )
                    x += name_w + spacing
                    addstr_clipped(
                        win,
                        line_y,
                        x,
                        f"{cont_name_clipped:<{col_container}}",
                        line_container_attr_final,
                    )
                    x += col_container + spacing
                    addstr_clipped(
                        win, line_y, x, f"{cpu_perc_s:>{col_cpu}}", line_cpu_attr
                    )
                    x += col_cpu + spacing
                    addstr_clipped(
                        win, line_y, x, f"{mem_perc_s:>{col_mem}}", mem_perc_attr
                    )
                    x += col_mem + spacing
                    rss_formatted = f"{rss_display:>{col_rss}}"
                    final_rss_text = f"{rss_formatted:<{col_rss_real_width}}"
                    addstr_clipped(win, line_y, x, final_rss_text, line_rss_attr)
                else:
                    user_clipped = user[:col_user]
                    docker_info_clipped = docker_info[:col_container_norm]
                    addstr_clipped(win, line_y, x, f"{pid_s:<{col_pid}}", line_attr)
                    x += col_pid + spacing
                    addstr_clipped(
                        win, line_y, x, f"{user_clipped:<{col_user}}", line_user_attr
                    )
                    x += col_user + spacing
                    addstr_clipped(
                        win, line_y, x, f"{cpu_perc_s:>{col_cpu}}", line_cpu_attr
                    )
                    x += col_cpu + spacing
                    addstr_clipped(
                        win, line_y, x, f"{mem_perc_s:>{col_mem}}", mem_perc_attr
                    )
                    x += col_mem + spacing
                    addstr_clipped(
                        win, line_y, x, f"{rss_display:>{col_rss}}", line_rss_attr
                    )
                    x += col_rss + spacing
                    addstr_clipped(win, line_y, x, f"{vms_mb_s:>{col_vms}}", vms_attr)
                    x += col_vms + spacing
                    addstr_clipped(
                        win,
                        line_y,
                        x,
                        f"{docker_info_clipped:<{col_container_norm}}",
                        line_container_attr_final,
                    )
                    x += col_container_norm + spacing
                    display_name_clipped = display_name[:proc_cmd_real_width]
                    final_name_text = f"{display_name_clipped:<{proc_cmd_real_width}}"
                    addstr_clipped(win, line_y, x, final_name_text, line_cmd_attr)
            except curses.error:
                pass
            procs_drawn_count += 1
        if not is_selecting:
            save_current_rss_state(current_rss_to_save)
    except curses.error:
        pass
    except Exception as e:
        try:
            if win and h > 1 and w > 1:
                error_y = h - 2
                error_msg = f"DrawErr:{type(e).__name__}"
                max_err_len = w - 4
                error_msg_clipped = error_msg[:max_err_len]
                if error_y > 0:
                    win.move(error_y, 1)
                    win.clrtoeol()
                    error_attr = (
                        curses.color_pair(4) | curses.A_BOLD
                        if has_colors
                        else curses.A_REVERSE
                    )
                    addstr_clipped(win, error_y, 2, error_msg_clipped, error_attr)
        except:
            pass
    return procs_drawn_count
