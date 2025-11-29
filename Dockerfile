FROM python:3.11-slim

WORKDIR /app

RUN pip install flask

COPY dice_roll.py .

EXPOSE 5000

CMD ["python", "dice_roll.py"]
