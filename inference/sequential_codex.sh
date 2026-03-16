#!/usr/bin/env bash
#
# Run the sequential adaptive environment with OpenAI Codex CLI as the solver.
#
# Usage:
#   bash inference/sequential_codex.sh [OPTIONS]
#
# Options (passed through to sequential_agent.py):
#   --num_questions N    Number of questions (default: 50)
#   --seed N             Random seed (default: 42)
#   --context_mode MODE  "summary" or "full_trace" (default: summary)
#   --correct N          Points for correct (default: 1)
#   --incorrect N        Points for incorrect (default: -10)
#   --skip N             Points for skip (default: 0)
#   --save_path PATH     Results JSONL path
#
# Script-only options (not passed to sequential_agent.py):
#   --model MODEL        Model to use (REQUIRED, e.g. gpt-5.2-codex, o4-mini)
#   --stream             Stream Codex's output in real time (JSONL events)
#   --timeout N          Max seconds per question before forcing answer (default: 180)
#
# Requires: codex CLI, jq

set -euo pipefail

# Defaults
SAVE_PATH="inference/results/seq_codex.jsonl"
STATE_PATH=""
AGENT_ARGS=()
SESSION_ID=""
MODEL=""
STREAM=false
TIMEOUT=180
FORCE_TIMEOUT=30
MAX_RETRIES=3
RETRY_DELAYS=(5 15 30)

# Parse args — pass everything through to sequential_agent.py,
# but intercept --save_path, --stream, --timeout for our own use
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --stream)
            STREAM=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --save_path)
            SAVE_PATH="$2"
            AGENT_ARGS+=("$1" "$2")
            shift 2
            ;;
        *)
            AGENT_ARGS+=("$1")
            shift
            ;;
    esac
done

# If --save_path not in args, add default
if [[ ! " ${AGENT_ARGS[*]:-} " =~ " --save_path " ]]; then
    AGENT_ARGS+=("--save_path" "$SAVE_PATH")
fi

# Model is required
if [[ -z "$MODEL" ]]; then
    echo "ERROR: --model is required (e.g. --model gpt-5.2-codex, --model o4-mini)" >&2
    exit 1
fi

STATE_PATH="${SAVE_PATH%.jsonl}.state.json"
LOG_PATH="${SAVE_PATH%.jsonl}.log"
TMP_STREAM=$(mktemp /tmp/codex_stream.XXXXXX)
trap 'rm -f "$TMP_STREAM"' EXIT

# Safety: read-only sandbox, skip git repo check
# Note: `codex exec resume` does NOT support --sandbox or -o, so resume calls
# use RESUME_FLAGS with -c to set sandbox policy instead.
SAFETY_FLAGS=(--sandbox read-only --skip-git-repo-check)
RESUME_FLAGS=(--skip-git-repo-check -c 'sandbox_permissions=["disk-full-read-access"]')

FORCE_PROMPT='TIME IS UP. You must respond IMMEDIATELY with one of:
1. Your best answer in \boxed{} if you have any guess at all
2. The word SKIP if you want to skip
Do NOT explain. Do NOT think further. Just \boxed{answer} or SKIP. NOW.'

echo "=== Sequential Environment with Codex CLI ==="
echo "Model: $MODEL"
echo "Save path: $SAVE_PATH"
echo "State path: $STATE_PATH"
echo "Log: $LOG_PATH"
echo "Streaming: $STREAM"
echo "Timeout: ${TIMEOUT}s per question (${FORCE_TIMEOUT}s for forced follow-up)"
echo ""

# --- Helper: call Codex, returns 0=success, 1=failure, 2=timeout ---
# Sets global $response and (on first call) $SESSION_ID
call_codex() {
    local time_limit="$1"
    local prompt="$2"
    local system_prompt="${3:-}"   # only used on first call (non-resume)
    local exit_code=0

    if $STREAM; then
        # Streaming mode: JSONL events
        echo ""
        > "$TMP_STREAM"

        if [[ -n "$SESSION_ID" ]]; then
            # Resume existing session
            timeout --kill-after=5 "$time_limit" codex exec resume "$SESSION_ID" \
                --json \
                --model "$MODEL" \
                "${RESUME_FLAGS[@]}" \
                "$prompt" > "$TMP_STREAM" 2>>"$LOG_PATH" &
        else
            # First call with developer instructions
            timeout --kill-after=5 "$time_limit" codex exec \
                --json \
                --model "$MODEL" \
                "${SAFETY_FLAGS[@]}" \
                -c "developer_instructions=\"$system_prompt\"" \
                "$prompt" > "$TMP_STREAM" 2>>"$LOG_PATH" &
        fi
        local codex_pid=$!

        # Live display of agent_message text events
        tail -f "$TMP_STREAM" --pid=$codex_pid 2>/dev/null | \
            jq -rj 'select(.type == "item.completed" and .item.type == "agent_message") | .item.text' 2>/dev/null &
        local display_pid=$!

        # Wait for codex to finish
        wait $codex_pid 2>/dev/null || exit_code=$?

        # Kill the display tail+jq
        kill $display_pid 2>/dev/null; wait $display_pid 2>/dev/null || true

        echo ""

        if (( exit_code == 124 || exit_code == 137 )); then
            # Timeout — try to extract partial response and session ID
            local partial
            partial=$(jq -r 'select(.type == "item.completed" and .item.type == "agent_message") | .item.text' "$TMP_STREAM" 2>/dev/null | tail -1 || true)

            # Extract thread_id even on timeout
            local tid
            tid=$(jq -r 'select(.type == "thread.started") | .thread_id' "$TMP_STREAM" 2>/dev/null | head -1 || true)
            if [[ -n "$tid" && "$tid" != "null" ]]; then
                SESSION_ID="$tid"
            fi

            if [[ -n "$partial" ]] && echo "$partial" | grep -q '\\boxed{'; then
                response="$partial"
                return 0
            fi
            return 2
        fi

        if (( exit_code != 0 )); then
            return 1
        fi

        # Extract thread_id and response from the JSONL stream
        local tid
        tid=$(jq -r 'select(.type == "thread.started") | .thread_id' "$TMP_STREAM" 2>/dev/null | head -1)
        if [[ -n "$tid" && "$tid" != "null" ]]; then
            SESSION_ID="$tid"
        fi
        response=$(jq -r 'select(.type == "item.completed" and .item.type == "agent_message") | .item.text' "$TMP_STREAM" 2>/dev/null | tail -1)
        if [[ -n "$response" && "$response" != "null" ]]; then
            return 0
        fi
        return 1
    else
        # Non-streaming mode: use --json to capture JSONL events (needed to
        # extract thread_id for session resume, and because resume doesn't
        # support -o).
        > "$TMP_STREAM"

        if [[ -n "$SESSION_ID" ]]; then
            # Resume existing session
            timeout --kill-after=5 "$time_limit" codex exec resume "$SESSION_ID" \
                --json \
                --model "$MODEL" \
                "${RESUME_FLAGS[@]}" \
                "$prompt" > "$TMP_STREAM" 2>>"$LOG_PATH" || exit_code=$?
        else
            # First call with developer instructions
            timeout --kill-after=5 "$time_limit" codex exec \
                --json \
                --model "$MODEL" \
                "${SAFETY_FLAGS[@]}" \
                -c "developer_instructions=\"$system_prompt\"" \
                "$prompt" > "$TMP_STREAM" 2>>"$LOG_PATH" || exit_code=$?
        fi

        if (( exit_code == 124 || exit_code == 137 )); then
            return 2
        fi

        if (( exit_code != 0 )); then
            return 1
        fi

        # Extract thread_id and response from JSONL events
        local tid
        tid=$(jq -r 'select(.type == "thread.started") | .thread_id' "$TMP_STREAM" 2>/dev/null | head -1)
        if [[ -n "$tid" && "$tid" != "null" ]]; then
            SESSION_ID="$tid"
        fi
        response=$(jq -r 'select(.type == "item.completed" and .item.type == "agent_message") | .item.text' "$TMP_STREAM" 2>/dev/null | tail -1)
        if [[ -n "$response" && "$response" != "null" ]]; then
            # Show a preview of the response
            local preview
            preview=$(echo "$response" | head -c 1000)
            echo ""
            echo "$preview"
            if (( ${#response} > 1000 )); then
                echo "... [truncated, ${#response} chars total]"
            fi
            return 0
        fi
        return 1
    fi
}

# --- Helper: call Codex with retries, timeout handling, and forced follow-up ---
# Sets $response and $OUTCOME_OVERRIDE
call_codex_with_retries() {
    local prompt="$1"
    local system_prompt="${2:-}"
    local attempt=0

    OUTCOME_OVERRIDE=""

    while (( attempt < MAX_RETRIES )); do
        local rc=0
        call_codex "$TIMEOUT" "$prompt" "$system_prompt" || rc=$?

        if (( rc == 0 )); then
            return 0
        fi

        if (( rc == 2 )); then
            # Timeout — try forced follow-up
            echo "  [TIMEOUT] Codex timed out after ${TIMEOUT}s. Forcing immediate answer..."

            if [[ -n "$SESSION_ID" ]]; then
                local force_rc=0
                call_codex "$FORCE_TIMEOUT" "$FORCE_PROMPT" "" || force_rc=$?

                if (( force_rc == 0 )); then
                    echo "  [TIMEOUT] Forced follow-up succeeded."
                    return 0
                fi
            fi

            # Forced follow-up also failed — record as timed_out
            echo "  [TIMEOUT] Forced follow-up failed. Recording as timed_out (0 reward)."
            response=""
            OUTCOME_OVERRIDE="timed_out"
            return 0
        fi

        # rc == 1: normal failure, retry
        attempt=$((attempt + 1))
        if (( attempt < MAX_RETRIES )); then
            local delay=${RETRY_DELAYS[$attempt - 1]:-30}
            echo "  [RETRY] Codex call failed (attempt $attempt/$MAX_RETRIES). Retrying in ${delay}s..."
            echo "  [RETRY] Check $LOG_PATH for details"
            sleep "$delay"
        fi
    done

    # All retries exhausted
    echo "  [ERROR] Codex call failed after $MAX_RETRIES attempts."
    echo "  [ERROR] Check $LOG_PATH for details"
    response=""
    return 1
}

while true; do
    # Get the current question
    question_json=$(python inference/sequential_agent.py \
        "${AGENT_ARGS[@]}" \
        --state "$STATE_PATH" \
        --action get_question 2>>"$LOG_PATH")

    msg_type=$(echo "$question_json" | jq -r '.type')

    if [[ "$msg_type" == "done" ]]; then
        echo ""
        echo "=== ENVIRONMENT COMPLETE ==="
        echo "$question_json" | jq .
        break
    fi

    step_num=$(echo "$question_json" | jq -r '.step')
    total=$(echo "$question_json" | jq -r '.total')
    score=$(echo "$question_json" | jq -r '.cumulative_score')
    system_prompt=$(echo "$question_json" | jq -r '.system_prompt')
    user_prompt=$(echo "$question_json" | jq -r '.user_prompt')

    echo "--- Step $step_num/$total (score: $score) ---"

    # Call Codex CLI with timeout + retry + forced follow-up
    response=""
    OUTCOME_OVERRIDE=""
    call_codex_with_retries "$user_prompt" "$system_prompt"

    # Submit the response
    SUBMIT_ARGS=("${AGENT_ARGS[@]}" --state "$STATE_PATH" --action submit --response "$response")
    if [[ -n "$OUTCOME_OVERRIDE" ]]; then
        SUBMIT_ARGS+=(--outcome_override "$OUTCOME_OVERRIDE")
    fi

    result_json=$(python inference/sequential_agent.py "${SUBMIT_ARGS[@]}" 2>>"$LOG_PATH")

    outcome=$(echo "$result_json" | jq -r '.outcome')
    delta=$(echo "$result_json" | jq -r '.score_delta')
    new_score=$(echo "$result_json" | jq -r '.cumulative_score')

    echo "  => $outcome ($delta) | cumulative: $new_score"
    echo ""
done

echo ""
echo "Results saved to: $SAVE_PATH"
