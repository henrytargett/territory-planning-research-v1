"""Application constants and configuration values."""

# API Timeouts (seconds)
TAVILY_API_TIMEOUT = 30.0
LLM_API_TIMEOUT = 60.0
HTTP_REQUEST_TIMEOUT = 120.0

# Retry Configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # Base delay for exponential backoff (seconds)
RETRY_MAX_DELAY = 30.0  # Maximum delay between retries

# Rate Limiting
DELAY_BETWEEN_COMPANIES = 1.0  # Seconds to wait between processing companies

# Job Health Monitoring
JOB_STALL_THRESHOLD = 300  # Seconds of inactivity before job is considered stalled
FRONTEND_POLL_INTERVAL = 3000  # Milliseconds

# Cost Estimation (USD)
TAVILY_COST_PER_CREDIT = 0.008  # $0.008 per credit
TAVILY_BASIC_CREDITS = 1
TAVILY_ADVANCED_CREDITS = 2

# LLM Parameters
LLM_TEMPERATURE = 0.3
LLM_TOP_P = 0.9
LLM_MAX_TOKENS = 2048

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    # Add production domains here, e.g.:
    # "https://yourdomain.com",
]

# Database
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10

# File Upload
MAX_CSV_SIZE_MB = 10
MAX_COMPANIES_PER_JOB = 500
