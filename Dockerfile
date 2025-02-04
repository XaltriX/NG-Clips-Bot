FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install FFmpeg (required for MoviePy)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy bot files
COPY . .

# Set environment variables (optional, replace with your actual values)
ENV TOKEN="8083480600:AAGiwI__cQ9MpwXE7Uy50WIZPXWRwufuiqI"

# Run the bot
CMD ["python3", "bot.py"]
