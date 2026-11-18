FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agenteval agenteval
COPY golden golden
COPY baseline.json .
ENTRYPOINT ["python", "-m", "agenteval.cli"]
CMD ["run"]
