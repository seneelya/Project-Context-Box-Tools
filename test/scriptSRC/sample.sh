#!/usr/bin/env bash
# setup
set -e
VAR=1

# build it
function build {
    local x=$1
    for f in a b; do
        echo "$f"
    done
    if [ -n "$x" ]; then
        echo yes
    elif [ -z "$x" ]; then
        echo no
    else
        echo maybe
    fi
}

run() {
    while true; do
        case "$1" in
            a) echo a ;;
            *) break ;;
        esac
    done
    cat <<EOT
heredoc $VAR
EOT
}

build "$@"
