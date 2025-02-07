# TRMNL MBTA Schedule Display

A real-time MBTA schedule display application for TRMNL eink displays. This application allows users to:

1. Configure specific MBTA routes they want to monitor
2. Fetch real-time schedule data from the MBTA API
3. Display schedule updates on their TRMNL eink display

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your MBTA API key:
   ```
   MBTA_API_KEY=your_api_key_here
   TRMNL_WEBHOOK_URL=your_trmnl_webhook_url
   ```
4. Run the application:
   ```bash
   python -m uvicorn main:app --reload
   ```

## Configuration

Edit the `config.json` file to specify which routes you want to monitor:

```json
{
  "routes": ["Red", "Green-B"],
  "stops": ["place-pktrm", "place-harsq"]
}
```

## API Documentation

The application provides the following endpoints:

- `POST /webhook/update`: Receives updates from MBTA and forwards to TRMNL
- `GET /config`: Get current route configuration
- `POST /config`: Update route configuration

## License

MIT License - See LICENSE file for details
