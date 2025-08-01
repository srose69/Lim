#!/bin/bash

_lim_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    opts="tui list l nav go inspect i updatecache tp help"

    if [ ${COMP_CWORD} -eq 1 ]; then
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
        return 0
    fi

    local command="${COMP_WORDS[1]}"
    case "${command}" in
        inspect|i|go)
            local containers
            local cache_file="$HOME/.config/lim/docker_cache.json"
            if [ -f "$cache_file" ] && command -v jq &> /dev/null; then
                containers=$(jq -r '.containers[].name,.containers[].short_id' "$cache_file" 2>/dev/null)
            fi
            if [ -z "$containers" ]; then
                containers=$(docker ps --format "{{.Names}} {{.ID}}" 2>/dev/null)
            fi
            COMPREPLY=($(compgen -W "${containers}" -- "${cur}"))
            ;;

        tp)
            # Автодополнение для sub-команд tp
            local tp_opts="add del list"
            local bookmarks_file="$HOME/.config/lim/bookmarks.json"

            if [ ${COMP_CWORD} -eq 2 ]; then
                local bookmark_names
                if [ -f "$bookmarks_file" ] && command -v jq &> /dev/null; then
                    bookmark_names=$(jq -r 'keys | .[]' "$bookmarks_file" 2>/dev/null)
                fi
                COMPREPLY=($(compgen -W "${tp_opts} ${bookmark_names}" -- "${cur}"))
            
            elif [ ${COMP_CWORD} -eq 3 ] && [[ "${COMP_WORDS[2]}" == "del" ]]; then
                # Автодополнение для `lim tp del <bookmark>`
                local bookmark_names
                if [ -f "$bookmarks_file" ] && command -v jq &> /dev/null; then
                    bookmark_names=$(jq -r 'keys | .[]' "$bookmarks_file" 2>/dev/null)
                fi
                COMPREPLY=($(compgen -W "${bookmark_names}" -- "${cur}"))
            fi
            ;;
        *)
            ;;
    esac
    return 0
}

complete -F _lim_completion lim