FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY terrain.py server.py launch.py runtime_paths.py ATTRIBUTION.txt ./
COPY static ./static
RUN mkdir -p /app/data /app/exports
VOLUME ["/app/data", "/app/exports"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status',timeout=3)"
CMD ["python", "launch.py", "--no-browser"]
