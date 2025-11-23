# StreamToy Quick Start Guide

## Installation (One Command)

```bash
sudo ./install.sh
```

Then reboot:
```bash
sudo reboot
```

That's it! The app will start automatically after reboot.

---

## Common Commands

### Service Control
```bash
# Status
sudo systemctl status stream_toy

# Stop
sudo systemctl stop stream_toy

# Start
sudo systemctl start stream_toy

# Restart
sudo systemctl restart stream_toy

# View logs (live)
sudo journalctl -u stream_toy -f
```

### Exit the App (Development)
**Long-press the bottom-right button (⚙ gear icon)** on the main launcher screen

### Manual Run (Testing)
```bash
sudo systemctl stop stream_toy
cd /opt/stream_toy
source .venv/bin/activate
export PYTHONPATH=/opt/stream_toy/StreamDock-Device-SDK/Python-Linux-SDK/src
python3 main.py
```

### Update Installation
```bash
cd /path/to/source
sudo ./install.sh
sudo systemctl restart stream_toy
```

### Uninstall
```bash
sudo ./uninstall.sh
```

---

## Key Locations

| Item | Path |
|------|------|
| App | `/opt/stream_toy/` |
| Logs | `sudo journalctl -u stream_toy` |
| Settings | `/opt/stream_toy/data/.settings.yml` |
| Service | `/etc/systemd/system/stream_toy.service` |

---

## Troubleshooting

**Service not starting?**
```bash
sudo journalctl -u stream_toy -n 50
```

**No audio?**
```bash
speaker-test -t wav -c 2 -l 1
```

**StreamDock not detected?**
```bash
ls -la /dev/bus/usb/001/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Need to reboot?**
```bash
sudo reboot
```

---

## Full Documentation

- **[INSTALL.md](INSTALL.md)** - Complete installation guide
- **[README.md](README.md)** - Hardware documentation and system requirements
- **[CLAUDE.md](CLAUDE.md)** - Project architecture and development guidelines

---

## License

This project is licensed under **CC BY-NC-SA 4.0** (non-commercial).

- ✅ Free for personal, educational, and non-profit use
- ❌ Commercial use requires permission

Contact: streamtoy@sckoch.eu
