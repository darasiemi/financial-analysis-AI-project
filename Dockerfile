FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --frozen \
    --no-dev \
    --group deployment

COPY . .

EXPOSE 8501

CMD [ \
    "uv", \
    "run", \
    "--no-dev", \
    "--group", \
    "deployment", \
    "streamlit", \
    "run", \
    "deployment/app.py", \
    "--server.address=0.0.0.0", \
    "--server.port=8501"  \
]