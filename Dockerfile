# 기본 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBUG=False
ENV SECRET_KEY=django-insecure-k8^6bq1c^#x&)d^uv6p1%ys=l9a&@_6#=j=7=*4=y#5qj8!+*d
ENV ALLOWED_HOSTS=.railway.app,work-project-back-production.up.railway.app
ENV CORS_ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend-domain.vercel.app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사 및 설치
COPY requirements/base.txt .
RUN pip install --no-cache-dir -r base.txt

# 프로젝트 파일 복사
COPY . .

# 정적 파일 수집
RUN python manage.py collectstatic --noinput

# 포트 설정
EXPOSE 8000

# 실행 명령
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"] 