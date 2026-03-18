# Dockerfile.simple
# 简化版 - 适合Windows Docker Desktop

FROM python:3.9

WORKDIR /app

# 1. 先安装系统依赖
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. 复制requirements文件
COPY requirements_simple.txt .

# 3. 安装Python依赖
RUN pip install --upgrade pip && \
    pip install -r requirements_simple.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 复制应用代码
COPY . .

# 5. 启动命令
CMD ["python", "main.py"]