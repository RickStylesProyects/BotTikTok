# RS TikTok Downloader - Hugging Face Spaces Dockerfile
# Telegram bot with health check endpoint for HF Spaces

FROM python:3.11-slim

# Create non-root user (required by HF Spaces)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy requirements first for better caching
COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application files
COPY --chown=user . /app

# Create downloads directory
RUN mkdir -p /app/downloads

# Expose port for health check (required by HF Spaces)
EXPOSE 7860

# Run the bot with health server
CMD ["python", "main.py"]
