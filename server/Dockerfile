FROM python-local-offline

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first for better caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy app code
COPY . /app

# Expose typical dev/prod ports
EXPOSE 8000
EXPOSE 8443

# Default command (overridden by compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
