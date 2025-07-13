# Use an official Python image
FROM python:3.13-slim-bookworm

# Set working directory
WORKDIR /app

# Copy the application code
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir fastapi httpx uvicorn

# Expose the port FastAPI will listen on
EXPOSE 8000

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "loadbalancer:app", "--host", "0.0.0.0", "--port", "8000"]
