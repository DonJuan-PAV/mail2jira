FROM python:3.12-slim

# Show logs immediately (needed to see the sign-in code with docker logs)
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /app

# Install libraries first: Docker reuses this step if only the code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

CMD ["python", "src/main.py"]
