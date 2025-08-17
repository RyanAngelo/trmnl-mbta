# TRMNL MBTA Schedule Display

A lightweight command-line application that fetches real-time MBTA schedule data and updates TRMNL eink displays.

## Quick Start

1. **Get API Keys**:
   - MBTA API key: https://api-v3.mbta.com/
   - TRMNL webhook URL: From your TRMNL dashboard

2. **Setup**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run**:
   ```bash
   # Test once
   python cli.py --once
   
   # Run continuously
   python cli.py
   
   # Change route
   python cli.py --route Red
   ```

## Configuration

Create `.env` file:
```ini
MBTA_API_KEY=your_mbta_api_key_here
TRMNL_WEBHOOK_URL=your_trmnl_webhook_url_here
DEBUG_MODE=false
```

## Usage

```bash
# Run once and exit
python cli.py --once

# Run continuously (30-second intervals)
python cli.py

# Custom interval
python cli.py --interval 60

# Change route
python cli.py --route Red --once
```

## Running as a Service

**Systemd Service** (Linux):
```bash
sudo cp examples/systemd-service.txt /etc/systemd/system/trmnl-mbta.service
# Edit paths in service file
sudo systemctl enable trmnl-mbta
sudo systemctl start trmnl-mbta
```

**Cron Job**:
```bash
crontab -e
# Add: */5 * * * * cd /path/to/trmnl-mbta && python cli.py --once
```

## Requirements

- Python 3.7+
- MBTA API key
- TRMNL webhook URL