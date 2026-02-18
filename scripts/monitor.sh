#!/bin/bash
# monitor.sh - News Origin Docker 컨테이너 리소스 모니터링
#
# 사용법:
#   ./scripts/monitor.sh              # 전체 출력
#   ./scripts/monitor.sh --quiet      # 경고/알림이 있을 때만 출력
#   ./scripts/monitor.sh --webhook    # Discord 웹훅 알림 포함
#   ./scripts/monitor.sh --quiet --webhook
#
# 권장 크론탭 (매 5분):
#   */5 * * * * /home/zerolive/work/news-origin/scripts/monitor.sh --quiet --webhook >> /home/zerolive/work/news-origin/logs/monitor.log 2>&1
#
# 환경변수:
#   DISCORD_WEBHOOK_URL  Discord 웹훅 URL (또는 .env 파일에 설정)

set -euo pipefail

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

# ---------------------------------------------------------------------------
# 인수 파싱
# ---------------------------------------------------------------------------
QUIET=false
USE_WEBHOOK=false

for arg in "$@"; do
    case "$arg" in
        --quiet)   QUIET=true ;;
        --webhook) USE_WEBHOOK=true ;;
    esac
done

# ---------------------------------------------------------------------------
# 웹훅 URL 로드 (.env 파일 또는 환경변수)
# ---------------------------------------------------------------------------
WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
if [[ -z "$WEBHOOK_URL" && -f "$ENV_FILE" ]]; then
    WEBHOOK_URL="$(grep -E '^DISCORD_WEBHOOK_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"'"'" || true)"
fi

# ---------------------------------------------------------------------------
# 색상 (터미널 출력 전용)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    GREEN='\033[0;32m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED=''; YELLOW=''; GREEN=''; CYAN=''; BOLD=''; RESET=''
fi

# ---------------------------------------------------------------------------
# 컨테이너별 임계값 정의 (단위: MiB)
# ---------------------------------------------------------------------------
# 형식: "컨테이너명:경고MiB:위험MiB:mem_limitMiB"
# mem_limit은 80% 규칙 적용 시 참조용
declare -A WARN_MB=(
    [newsorigin-celery]=800
    [newsorigin-qdrant]=400
    [newsorigin-backend]=300
    [newsorigin-celery-beat]=102    # 128m * 80%
    [newsorigin-postgres]=102       # 128m * 80%
    [newsorigin-redis]=51           # 64m  * 80%
    [newsorigin-flower]=102         # 128m * 80%
    [newsorigin-frontend]=25        # 32m  * 80%
    [newsorigin-nginx]=51           # 64m  * 80%
)

declare -A CRIT_MB=(
    [newsorigin-celery]=950
    [newsorigin-qdrant]=480
    [newsorigin-backend]=360
    [newsorigin-celery-beat]=115    # 128m * 90%
    [newsorigin-postgres]=115       # 128m * 90%
    [newsorigin-redis]=57           # 64m  * 90%
    [newsorigin-flower]=115         # 128m * 90%
    [newsorigin-frontend]=28        # 32m  * 90%
    [newsorigin-nginx]=57           # 64m  * 90%
)

# ---------------------------------------------------------------------------
# 유틸리티 함수
# ---------------------------------------------------------------------------

# 메모리 문자열 "123.4MiB" 또는 "1.2GiB" → MiB 정수 변환
mem_to_mib() {
    local raw="$1"
    # docker stats 포맷: "123.4MiB" / "1.23GiB" / "456kB" 등
    local num unit
    num="$(echo "$raw" | sed 's/[A-Za-z]//g')"
    unit="$(echo "$raw" | sed 's/[0-9.]//g' | tr '[:lower:]' '[:upper:]')"
    case "$unit" in
        GIB|GB) printf '%.0f' "$(echo "$num * 1024" | bc -l 2>/dev/null || awk "BEGIN{printf \"%.0f\", $num * 1024}")" ;;
        MIB|MB) printf '%.0f' "$num" ;;
        KIB|KB) printf '%.0f' "$(echo "$num / 1024" | bc -l 2>/dev/null || awk "BEGIN{printf \"%.0f\", $num / 1024}")" ;;
        *)      echo "0" ;;
    esac
}

# 정렬된 상태 문자열 → 짧은 레이블
short_status() {
    local s="$1"
    case "$s" in
        running)   echo "OK" ;;
        unhealthy) echo "UNHEALTHY" ;;
        starting)  echo "STARTING" ;;
        exited)    echo "EXITED" ;;
        paused)    echo "PAUSED" ;;
        dead)      echo "DEAD" ;;
        *)         echo "$s" ;;
    esac
}

# ---------------------------------------------------------------------------
# 데이터 수집
# ---------------------------------------------------------------------------
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# docker stats --no-stream: 한 번만 샘플 수집
# 포맷: NAME|MEM_USAGE|MEM_PERC|CPU_PERC
STATS_RAW="$(docker stats --no-stream \
    --format '{{.Name}}|{{.MemUsage}}|{{.MemPerc}}|{{.CPUPerc}}' 2>/dev/null || true)"

# docker ps: 컨테이너 상태 수집
PS_RAW="$(docker ps -a \
    --format '{{.Names}}|{{.Status}}' 2>/dev/null || true)"

# ---------------------------------------------------------------------------
# 상태 맵 구성
# ---------------------------------------------------------------------------
declare -A CONTAINER_STATUS
while IFS='|' read -r name status; do
    [[ -z "$name" ]] && continue
    CONTAINER_STATUS["$name"]="$status"
done <<< "$PS_RAW"

# ---------------------------------------------------------------------------
# 결과 수집 (배열)
# ---------------------------------------------------------------------------
ALERT_LINES=()   # 상태/임계값 초과 경고
WARNING_LINES=() # 경고 수준

# 테이블 행을 담을 배열
TABLE_ROWS=()

# 알려진 컨테이너 목록 (표시 순서)
KNOWN_CONTAINERS=(
    newsorigin-celery
    newsorigin-backend
    newsorigin-qdrant
    newsorigin-redis
    newsorigin-postgres
    newsorigin-celery-beat
    newsorigin-flower
    newsorigin-nginx
    newsorigin-frontend
)

# stats 결과를 맵으로 변환
declare -A STATS_MAP
while IFS='|' read -r name mem_usage mem_perc cpu_perc; do
    [[ -z "$name" ]] && continue
    STATS_MAP["$name"]="$mem_usage|$mem_perc|$cpu_perc"
done <<< "$STATS_RAW"

# ---------------------------------------------------------------------------
# 각 컨테이너 처리
# ---------------------------------------------------------------------------
for cname in "${KNOWN_CONTAINERS[@]}"; do
    # 상태 조회
    raw_status="${CONTAINER_STATUS[$cname]:-N/A}"
    # docker ps Status 예: "Up 2 hours (healthy)", "Exited (1) ...", "Up 3 minutes"
    if echo "$raw_status" | grep -qi "unhealthy"; then
        state="unhealthy"
    elif echo "$raw_status" | grep -qi "^Up"; then
        state="running"
    elif echo "$raw_status" | grep -qi "exited\|dead"; then
        state="exited"
    elif echo "$raw_status" | grep -qi "starting\|health: starting"; then
        state="starting"
    elif [[ "$raw_status" == "N/A" ]]; then
        state="missing"
    else
        state="$raw_status"
    fi

    slabel="$(short_status "$state")"

    # 메모리/CPU 조회
    if [[ -n "${STATS_MAP[$cname]:-}" ]]; then
        IFS='|' read -r mem_usage mem_perc cpu_perc <<< "${STATS_MAP[$cname]}"
        # mem_usage 형식: "123.4MiB / 1GiB" → 앞부분만 추출
        mem_used_raw="$(echo "$mem_usage" | awk '{print $1}')"
        mem_used_mib="$(mem_to_mib "$mem_used_raw")"
        mem_limit_raw="$(echo "$mem_usage" | awk '{print $3}')"
        mem_display="${mem_used_raw} / ${mem_limit_raw}"
        cpu_display="$cpu_perc"
    else
        mem_used_mib=0
        mem_display="N/A"
        cpu_display="N/A"
        mem_perc="0.00%"
    fi

    # 임계값 비교
    warn_mb="${WARN_MB[$cname]:-9999}"
    crit_mb="${CRIT_MB[$cname]:-9999}"

    mem_level="OK"
    if [[ "$mem_used_mib" -ge "$crit_mb" ]] 2>/dev/null; then
        mem_level="CRITICAL"
    elif [[ "$mem_used_mib" -ge "$warn_mb" ]] 2>/dev/null; then
        mem_level="WARNING"
    fi

    # 알림 수집
    if [[ "$state" == "exited" || "$state" == "dead" || "$state" == "missing" ]]; then
        ALERT_LINES+=("ALERT: $cname is $slabel (status: $raw_status)")
    elif [[ "$state" == "unhealthy" ]]; then
        ALERT_LINES+=("ALERT: $cname is UNHEALTHY")
    fi

    if [[ "$mem_level" == "CRITICAL" ]]; then
        ALERT_LINES+=("CRITICAL: $cname memory ${mem_used_mib}MiB >= ${crit_mb}MiB threshold (${mem_display})")
    elif [[ "$mem_level" == "WARNING" ]]; then
        WARNING_LINES+=("WARNING: $cname memory ${mem_used_mib}MiB >= ${warn_mb}MiB threshold (${mem_display})")
    fi

    # 테이블 행 구성 (고정 너비 문자열)
    TABLE_ROWS+=("$(printf '%-28s %-22s %-10s %-12s %-10s' \
        "$cname" "$mem_display" "$mem_perc" "${cpu_display}" "$slabel")")
done

# ---------------------------------------------------------------------------
# 호스트 메모리 요약
# ---------------------------------------------------------------------------
HOST_MEM_LINE="$(free -m | awk 'NR==2 {printf "Host RAM: %dMiB used / %dMiB total (%.0f%%)", $3, $2, $3/$2*100}')"

# ---------------------------------------------------------------------------
# 출력 함수
# ---------------------------------------------------------------------------
print_table() {
    echo ""
    echo "${BOLD}${CYAN}=== News Origin Container Resources [${TIMESTAMP}] ===${RESET}"
    echo ""
    printf "${BOLD}%-28s %-22s %-10s %-12s %-10s${RESET}\n" \
        "CONTAINER" "MEMORY (used/limit)" "MEM%" "CPU%" "STATUS"
    printf '%s\n' "$(printf '%-28s %-22s %-10s %-12s %-10s' \
        "----------------------------" "----------------------" "----------" "------------" "----------")"

    # stats 기반 재처리하여 색상 적용
    for cname in "${KNOWN_CONTAINERS[@]}"; do
        raw_status="${CONTAINER_STATUS[$cname]:-N/A}"
        if echo "$raw_status" | grep -qi "unhealthy"; then
            state="unhealthy"; slabel="UNHEALTHY"
        elif echo "$raw_status" | grep -qi "^Up"; then
            state="running";   slabel="OK"
        elif echo "$raw_status" | grep -qi "exited\|dead"; then
            state="exited";    slabel="EXITED"
        elif echo "$raw_status" | grep -qi "starting"; then
            state="starting";  slabel="STARTING"
        elif [[ "$raw_status" == "N/A" ]]; then
            state="missing";   slabel="MISSING"
        else
            state="$raw_status"; slabel="$raw_status"
        fi

        if [[ -n "${STATS_MAP[$cname]:-}" ]]; then
            IFS='|' read -r mem_usage mem_perc cpu_perc <<< "${STATS_MAP[$cname]}"
            mem_used_raw="$(echo "$mem_usage" | awk '{print $1}')"
            mem_used_mib="$(mem_to_mib "$mem_used_raw")"
            mem_limit_raw="$(echo "$mem_usage" | awk '{print $3}')"
            mem_display="${mem_used_raw} / ${mem_limit_raw}"
            cpu_display="$cpu_perc"
        else
            mem_used_mib=0; mem_display="N/A"; cpu_display="N/A"; mem_perc="N/A"
        fi

        warn_mb="${WARN_MB[$cname]:-9999}"
        crit_mb="${CRIT_MB[$cname]:-9999}"

        # 행 색상 결정
        if [[ "$state" == "exited" || "$state" == "dead" || "$state" == "missing" || "$state" == "unhealthy" ]]; then
            row_color="$RED"
        elif [[ "$mem_used_mib" -ge "$crit_mb" ]] 2>/dev/null; then
            row_color="$RED"
        elif [[ "$mem_used_mib" -ge "$warn_mb" ]] 2>/dev/null; then
            row_color="$YELLOW"
        else
            row_color="$GREEN"
        fi

        printf "${row_color}%-28s %-22s %-10s %-12s %-10s${RESET}\n" \
            "$cname" "$mem_display" "$mem_perc" "$cpu_display" "$slabel"
    done

    echo ""
    echo "  $HOST_MEM_LINE"
    echo ""
}

print_alerts() {
    for line in "${WARNING_LINES[@]:-}"; do
        [[ -z "$line" ]] && continue
        echo "${YELLOW}${line}${RESET}"
    done
    for line in "${ALERT_LINES[@]:-}"; do
        [[ -z "$line" ]] && continue
        echo "${RED}${line}${RESET}"
    done
}

# ---------------------------------------------------------------------------
# Discord 웹훅 전송
# ---------------------------------------------------------------------------
send_discord() {
    [[ -z "$WEBHOOK_URL" ]] && return 0

    local total_alerts=$(( ${#ALERT_LINES[@]} + ${#WARNING_LINES[@]} ))
    local color
    if [[ "${#ALERT_LINES[@]}" -gt 0 ]]; then
        color=16711680   # 빨강
    else
        color=16776960   # 노랑
    fi

    # 알림 요약 텍스트 구성
    local alert_text=""
    for line in "${WARNING_LINES[@]:-}"; do
        [[ -z "$line" ]] && continue
        alert_text+="⚠ ${line}\n"
    done
    for line in "${ALERT_LINES[@]:-}"; do
        [[ -z "$line" ]] && continue
        alert_text+="🚨 ${line}\n"
    done

    # 테이블 요약 (plain text)
    local table_text=""
    for cname in "${KNOWN_CONTAINERS[@]}"; do
        if [[ -n "${STATS_MAP[$cname]:-}" ]]; then
            IFS='|' read -r mem_usage mem_perc cpu_perc <<< "${STATS_MAP[$cname]}"
            mem_used_raw="$(echo "$mem_usage" | awk '{print $1}')"
            mem_limit_raw="$(echo "$mem_usage" | awk '{print $3}')"
            short_name="${cname#newsorigin-}"
            table_text+="$(printf '%-14s %s / %s  CPU:%s\n' "$short_name" "$mem_used_raw" "$mem_limit_raw" "$cpu_perc")"
        fi
    done
    table_text+="\n$HOST_MEM_LINE"

    # JSON 이스케이프 (개행 → \n, 따옴표 → \")
    local escaped_alerts
    escaped_alerts="$(printf '%s' "$alert_text" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/' | tr -d '\n')"
    local escaped_table
    escaped_table="$(printf '%s' "$table_text" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/' | tr -d '\n')"

    local payload
    payload=$(cat <<EOF
{
  "embeds": [{
    "title": "News Origin 리소스 경고 (${total_alerts}건)",
    "color": ${color},
    "fields": [
      {
        "name": "경고 내용",
        "value": "${escaped_alerts}",
        "inline": false
      },
      {
        "name": "컨테이너 현황",
        "value": "\`\`\`\n${escaped_table}\`\`\`",
        "inline": false
      }
    ],
    "footer": { "text": "${TIMESTAMP}" }
  }]
}
EOF
)

    curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$WEBHOOK_URL" > /dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------
HAS_ALERTS=$(( ${#ALERT_LINES[@]} + ${#WARNING_LINES[@]} ))

if [[ "$QUIET" == "true" ]]; then
    # --quiet: 경고/알림이 있을 때만 출력
    if [[ "$HAS_ALERTS" -gt 0 ]]; then
        print_table
        print_alerts
        if [[ "$USE_WEBHOOK" == "true" ]]; then
            send_discord
        fi
    fi
else
    # 항상 출력
    print_table
    if [[ "$HAS_ALERTS" -gt 0 ]]; then
        print_alerts
        if [[ "$USE_WEBHOOK" == "true" ]]; then
            send_discord
        fi
    fi
fi

exit 0
