cp fritzmesh.py /usr/local/bin
chmod +x /usr/local/bin/fritzmesh.py
cp fritzmesh.service /etc/systemd/system
cp fritzmesh /etc
mkdir -p /var/cache/fritzmesh
systemctl enable fritzmesh
systemctl start fritzmesh