FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORK_DIR=/diff

COPY archsync_mcp.py ./archsync_mcp.py

RUN pip install --no-cache-dir fastmcp requests pydantic && \
    mkdir -p /diff

EXPOSE 8013

CMD ["python", "archsync_mcp.py"]
