FROM registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim

WORKDIR /app

RUN pip install flask -i https://mirrors.aliyun.com/pypi/simple/

COPY dice_roll.py .

EXPOSE 5000

CMD ["python", "dice_roll.py"]
