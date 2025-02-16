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
   ```

3. Configure your desired line in `config.json`:
   ```json
   {
     "route_id": "Orange"
   }
   ```

   Available route IDs:
   - Red
   - Orange
   - Blue
   - Green-B
   - Green-C
   - Green-D
   - Green-E

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

## Development

### Quick Setup

The project uses `make` commands to simplify development tasks. To get started:

```bash
# Install dependencies and set up development environment
make install

# Run tests
make test

# Format code
make format

# Run linting checks
make lint

# Sync dependencies between pyproject.toml and requirements.txt
make sync-deps

# Clean up build artifacts and cache files
make clean

# See all available commands
make help
```

### Running Tests

Run the test suite:
```bash
make test
```

### Code Style

This project uses:
- Black for code formatting
- isort for import sorting
- flake8 for linting

To check code style:
```bash
make lint
```

To automatically format code:
```bash
make format
```