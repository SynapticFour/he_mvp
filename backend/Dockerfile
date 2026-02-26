# SPDX-License-Identifier: Apache-2.0
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Run from backend dir so app and integrity/algorithms resolve
ENV SECURECOLLAB_DATABASE_URL=sqlite:///./data/secure_collab.db
ENV SECURECOLLAB_UPLOADS_DIR=/app/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
