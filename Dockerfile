# 기본 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

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