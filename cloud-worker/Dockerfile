FROM python:3.12-slim
# git: a lib da Gree é instalada do GitHub; build-essential: o netifaces (dependência dela) compila na instalação
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py mapeamento.py ./
CMD ["python", "-u", "main.py"]
