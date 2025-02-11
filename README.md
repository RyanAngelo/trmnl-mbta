# TRMNL MBTA Schedule Display

A real-time MBTA schedule display application for TRMNL eink displays. This application fetches and displays train arrival predictions for MBTA lines.



## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your API keys:
   ```
   MBTA_API_KEY=your_api_key_here
   TRMNL_WEBHOOK_URL=your_trmnl_webhook_url
   ```
4. Configure your desired line in `config.json`:
   ```json
   {
     "route_id": "Orange"
   }
   ```

## Running the Application

There are two ways to run the application:

### As a Web Server
```bash
python main.py
```
This runs a FastAPI server that:
- Provides configuration endpoints
- Updates the display every 30 seconds
- Allows manual updates via webhook

### As a Cron Job
```bash
python main.py --once
```
This:
- Runs a single update
- Exits after completion
- Perfect for cron jobs

Example crontab entry (updates every 5 minutes):
```bash
*/5 * * * * cd /path/to/project && /usr/bin/python3 main.py --once >> /path/to/mbta_cron.log 2>&1
```

## API Endpoints

- `GET /config`: Get current route configuration
- `POST /config`: Update route configuration
- `POST /webhook/update`: Manually trigger display update

## Supported Lines

- Red Line
- Orange Line
- Blue Line
- Green Line (B, C, D, E branches)

## License

MIT License - See LICENSE file for details
