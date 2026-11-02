# ============================================================
# 运行环境镜像：Python 运行环境 + 第三方依赖（前后端代码不打入镜像）
# 业务代码与前端产物由 docker-compose.yml 通过 volumes 外挂
#
#   docker build -t plains:base .
#
# 构建上下文需包含：backend/requirements.txt  wheels/(可为空目录)
# 依赖安装：wheels 目录非空 -> 离线安装；为空 -> 在线安装（需能访问 PyPI）
#
# 国内网络直连 docker.io / deb.debian.org / pypi.org 常超时：
# apt 与 pip 默认已走阿里云镜像，无需额外参数；若构建机可直连官方源，
# 用 --build-arg APT_MIRROR= --build-arg PIP_INDEX_URL= 还原。
# base 镜像拉不动时，给 FROM 换成镜像站地址：
#   docker build -t plains:base . \
#     --build-arg BASE_IMAGE=docker.m.daocloud.io/library/python:3.13-slim
# ============================================================

# 基础镜像（可换成任一镜像站的 python:3.13-slim 代理地址）
ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=Asia/Shanghai

# tzdata：要素编号用本地时间生成日期段，容器默认 UTC 会差 8 小时
# APT_MIRROR 默认走阿里云；构建机能直连官方源时传 --build-arg APT_MIRROR= 覆盖为空
ARG APT_MIRROR=mirrors.aliyun.com
# ForceIPv4：容器内 IPv6 常无路由，apt 会先试 AAAA 记录直到超时，表现为长时间"卡住"
RUN APT_OPTS="-o Acquire::Retries=3 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 -o Acquire::ForceIPv4=true"; \
    if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null \
        || sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list; \
    fi \
 && apt-get $APT_OPTS update \
 && apt-get $APT_OPTS install -y --no-install-recommends tzdata \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
 && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅拷贝依赖清单安装依赖，不打包业务代码（前后端代码通过挂载卷外挂）
COPY backend/requirements.txt /tmp/requirements.txt

# 离线优先：wheels 目录下存在 *.whl 时走离线安装，避免 .gitkeep 等占位文件误判
# 在线安装默认走阿里云 PyPI 镜像；传 --build-arg PIP_INDEX_URL= 则用官方源
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
COPY wheels/ /tmp/wheels/
RUN if [ -n "$(find /tmp/wheels -maxdepth 1 -name '*.whl' 2>/dev/null)" ]; then \
      echo ">>> 检测到离线 wheel 包，执行离线安装..."; \
      pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r /tmp/requirements.txt; \
    else \
      echo ">>> 未检测到离线 wheel 包，走在线源安装 (${PIP_INDEX_URL})..."; \
      pip install --no-cache-dir ${PIP_INDEX_URL:+-i "$PIP_INDEX_URL"} -r /tmp/requirements.txt; \
    fi \
 && rm -rf /tmp/wheels /tmp/requirements.txt

# 预先创建挂载点目录
RUN mkdir -p /app/backend /app/web/dist /app/backend/uploads

# 运行期默认值（--env-file 注入的同名变量优先级更高）
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8100 \
    WEB_DIST=/app/web/dist \
    UPLOAD_DIR=/app/backend/uploads

EXPOSE 8100
WORKDIR /app/backend

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('APP_PORT','8100')+'/api/health', timeout=3)"

CMD ["python", "serve.py"]
