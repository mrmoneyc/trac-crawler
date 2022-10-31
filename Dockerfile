FROM python:3.9-slim

ADD crawler/. /app
RUN chmod a+x /app/*.py

WORKDIR /app
RUN pip3 install -r requirements.txt

CMD ["python3", "/app/trac-crawler.py"]
