#!/usr/bin/env bash
# BSC RPC가 프록시를 쓰도록 HTTPS_PROXY를 설정한 뒤 gunicorn 실행.
# 사용: systemd ExecStart=/home/ubuntu/O-Bot/scripts/run_obot_gunicorn.sh
set -e
cd "$(dirname "$0")/.."
# systemd EnvironmentFile로 안 들어왔으면 .env에서 읽기 (PROXY, MULTISIG)
if [ -f .env ]; then
  [ -z "$OPINION_PROXY" ] && OPINION_PROXY=$(grep -E '^OPINION_PROXY=' .env | head -1 | cut -d= -f2- | tr -d '"' | xargs) || true
  [ -z "$OPINION_MULTISIG_1" ] && export OPINION_MULTISIG_1=$(grep -E '^OPINION_MULTISIG_1=' .env | head -1 | cut -d= -f2- | tr -d '"' | xargs) || true
  [ -z "$OPINION_MULTISIG_2" ] && export OPINION_MULTISIG_2=$(grep -E '^OPINION_MULTISIG_2=' .env | head -1 | cut -d= -f2- | tr -d '"' | xargs) || true
fi
# OPINION_PROXY=IP:PORT:USER:PASS → http://USER:PASS@IP:PORT
if [ -n "$OPINION_PROXY" ]; then
  IFS=: read -r px_ip px_port px_user px_pass <<< "$OPINION_PROXY"
  if [ -n "$px_ip" ] && [ -n "$px_port" ] && [ -n "$px_user" ] && [ -n "$px_pass" ]; then
    export HTTPS_PROXY="http://${px_user}:${px_pass}@${px_ip}:${px_port}"
    export HTTP_PROXY="http://${px_user}:${px_pass}@${px_ip}:${px_port}"
  fi
fi
exec ./venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 --timeout 120 app:app
