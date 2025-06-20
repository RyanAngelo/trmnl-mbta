# TRMNL MBTA Schedule Display

A real-time MBTA schedule display application for TRMNL eink displays.

## Security Notice

This project uses environment variables for sensitive configuration. Never commit the `.env` file to version control.

## API Keys and Environment Variables

### Required API Keys

1. **MBTA API Key**
   - Required for accessing MBTA schedule data
   - Get one at https://api-v3.mbta.com/
   - Free tier available with rate limits
   - Sign up process:
     1. Visit https://api-v3.mbta.com/
     2. Click "Get Started"
     3. Fill out the registration form
     4. Your API key will be emailed to you

2. **TRMNL Webhook URL**
   - Required for updating your TRMNL display
   - Get this from your TRMNL dashboard
   - Format: `https://api.trmnl.com/...`

3. **Application API Key**
   - Used to secure the application's endpoints
   - Generate a secure random string (recommended: 32+ characters)
   - Example: `openssl rand -hex 32`

### Setting Up Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual credentials:
   ```ini
   # MBTA API key from api-v3.mbta.com
   MBTA_API_KEY=your_mbta_api_key_here
   
   # TRMNL webhook URL from your TRMNL dashboard
   TRMNL_WEBHOOK_URL=your_trmnl_webhook_url_here
   
   # Your application API key (generate with: openssl rand -hex 32)
   API_KEY=your_generated_api_key_here
   
   # Comma-separated list of allowed origins for CORS
   ALLOWED_ORIGINS=http://localhost:8000,https://your-domain.com
   
   # Debug mode settings
   # Set to true to enable debug mode (outputs to console or file instead of sending to TRMNL)
   DEBUG_MODE=false
   
   # Path to debug output file (leave empty to output to console)
   DEBUG_OUTPUT_FILE=debug_output.txt
   ```

3. Verify your configuration:
   ```bash
   python run.py --once
   ```
   This will attempt to fetch and display schedule data once.

### API Authentication

When making requests to the application's endpoints, include your API key in the header:
```bash
curl -H "X-API-Key: your_api_key_here" http://localhost:8000/config
```

## Requirements

- Python 3.7 or higher
- MBTA API key (get one at https://api-v3.mbta.com/)
- TRMNL webhook URL for your display

## Installation

### From Source

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/trmnl-mbta.git
   cd trmnl-mbta
   ```

2. Install the package with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

### Using pip

```bash
pip install trmnl-mbta
```

## Configuration

1. Create a `.env` file with your API keys and settings:
   ```bash
   cp .env.example .env
   ```

2. Configure your environment variables in `.env`:
   ```ini
   # MBTA API key from api-v3.mbta.com
   MBTA_API_KEY=your_mbta_api_key_here
   
   # TRMNL webhook URL from your TRMNL dashboard
   TRMNL_WEBHOOK_URL=your_trmnl_webhook_url_here
   
   # Your application API key (generate with: openssl rand -hex 32)
   API_KEY=your_generated_api_key_here
   
   # Comma-separated list of allowed origins for CORS
   ALLOWED_ORIGINS=http://localhost:8000,https://your-domain.com
   
   # Debug mode settings
   # Set to true to enable debug mode (outputs to console or file instead of sending to TRMNL)
   DEBUG_MODE=false
   
   # Path to debug output file (leave empty to output to console)
   DEBUG_OUTPUT_FILE=debug_output.txt
   ```

3. Configure your desired line in `config.json`:
   ```json
   {
     "route_id": "Orange"
   }
   ```

   Available route IDs:
   - **Subway Lines:**
     - Red
     - Orange
     - Blue
     - Green-B
     - Green-C
     - Green-D
     - Green-E
   
   - **Bus Routes:**
     - Any numeric route (e.g., "1", "66", "501")
     - Silver Line routes (e.g., "SL1", "SL2", "SL3", "SL4", "SL5", "SLW")
     - Express routes (e.g., "170", "171", "325", "326")
     - Commuter routes (e.g., "350", "351", "352", "354", "355")
     - All other MBTA bus routes

   **Note:** Bus routes are dynamically fetched from the MBTA API and will display stops in their proper sequence order. Unlike subway lines which have predefined stop orders, bus routes will show stops as they appear along the route.

### Route Switching Utility

The application includes a utility script to easily switch between different routes for testing:

```bash
# Switch to a subway line
python scripts/switch_route.py Orange

# Switch to a bus route
python scripts/switch_route.py 66

# Switch to Silver Line
python scripts/switch_route.py SL1

# Switch to express bus
python scripts/switch_route.py 501
```

This script updates your `config.json` file with the specified route ID. It's useful for:
- Testing different routes quickly
- Switching between subway and bus routes
- Verifying that your display works with various route types

### Security Configuration

#### API Key Protection
All API endpoints are protected by API key authentication. You must include the API key in the `X-API-Key` header for requests:
```bash
curl -H "X-API-Key: your_api_key_here" http://localhost:8000/config
```

#### CORS Configuration
Cross-Origin Resource Sharing (CORS) is configured using the `ALLOWED_ORIGINS` environment variable. This should be a comma-separated list of allowed origins:
```ini
ALLOWED_ORIGINS=http://localhost:8000,https://your-domain.com
```

The CORS configuration:
- Allows specified origins only
- Allows GET and POST methods
- Allows Content-Type, Authorization, and X-API-Key headers
- Exposes rate limit headers
- Caches preflight requests for 1 hour

### Rate Limits
The API endpoints have the following rate limits:
- GET /config: 60 requests per minute
- POST /config: 10 requests per minute
- POST /webhook/update: 30 requests per minute

## Usage

### Running as a Web Server

Start the web server:
```bash
python run.py
```

The server will start on http://localhost:8000 with the following endpoints:
- GET /config - Get current configuration
- POST /config - Update configuration
- POST /webhook/update - Manually trigger an update

### Running Once

To run once and exit (useful for cron jobs):
```bash
python run.py --once
```

### Debug Mode

For development and troubleshooting without a TRMNL display, you can enable debug mode:

1. Set `DEBUG_MODE=true` in your `.env` file, or
2. Set it temporarily via environment variable:
   ```bash
   DEBUG_MODE=true python run.py --once
   ```

Debug mode will:
- Skip sending updates to TRMNL
- Output a formatted table of predictions to the console or log file
- Show all stops with their inbound and outbound predictions
- Include timestamps for when the data was fetched
- Display up to 3 predictions per direction for each stop

Example debug output:
```
2024-04-06 14:30:45,123 - src.mbta.main - INFO - Debug output:
=== Orange Line Predictions (2024-04-06 14:30:45) ===
Last Updated: 2:30p

Stop Name          | Inbound 1 | Outbound 1 | Inbound 2 | Outbound 2 | Inbound 3 | Outbound 3
------------------|-----------|------------|-----------|------------|-----------|------------
Oak Grove         |     2:35p |      2:40p |     2:50p |      2:55p |     3:05p |      3:10p
Malden Center     |     2:37p |      2:38p |     2:52p |      2:53p |     3:07p |      3:08p
Wellington        |     2:40p |      2:35p |     2:55p |      2:50p |     3:10p |      3:05p
```

The `--once` flag is particularly useful with debug mode as it will run once and exit, making it easier to see the output without the continuous update loop.

## Display Format

The application uses a TRMNL-specific template format to display MBTA schedule information. The template consists of a single root div element containing a table layout (no HTML/HEAD tags), showing up to 12 stops with their inbound and outbound predictions. The display updates every 30 seconds and includes:

- Line name and color
- Last updated time
- For each stop:
  - Stop name
  - Next 2 inbound predictions
  - Next 2 outbound predictions

### Template Variables

The template uses a compact variable naming scheme to minimize payload size:

Header Variables:
- `{{l}}`: Line name (e.g., "Red", "Orange", "Blue")
- `{{c}}`: Line color in hex format (e.g., "#FA2D27" for Red Line)
- `{{u}}`: Last updated time in short format (e.g., "2:15p")

Stop Variables (where X is the stop index from 0-11):
- `{{nX}}`: Stop name (e.g., "n0" = "Assembly")
- `{{iX1}}`: First inbound prediction time (e.g., "i01" = "2:15p")
- `{{iX2}}`: Second inbound prediction time (e.g., "i02" = "2:30p")
- `{{oX1}}`: First outbound prediction time (e.g., "o01" = "2:20p")
- `{{oX2}}`: Second outbound prediction time (e.g., "o02" = "2:35p")

Example for Assembly station (index 0):
```
Stop Name: {{n0}} = "Assembly"
Inbound:   {{i01}} = "2:15p", {{i02}} = "2:30p"
Outbound:  {{o01}} = "2:20p", {{o02}} = "2:35p"
```

Note: The template must be a single root element without HTML or HEAD tags, as per TRMNL's requirements. All styling is done inline to ensure compatibility.