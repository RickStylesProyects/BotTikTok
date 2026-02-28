# RS TikTok Downloader - Hugging Face Spaces Dockerfile
# Telegram bot with health check endpoint for HF Spaces

FROM python:3.11-slim

# Create non-root user (required by HF Spaces)
RUN useradd -m -u 1000 user

WORKDIR /app

# Copy requirements first for better caching
COPY ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application files
COPY . /app

# Create downloads directory and set permissions
RUN mkdir -p /app/downloads && chown -R user:user /app

USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Expose port for health check (required by HF Spaces)
EXPOSE 7860

# Run the bot with health server
CMD ["python", "main.py"]
