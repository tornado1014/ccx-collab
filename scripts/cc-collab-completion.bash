#!/bin/bash
# Bash completion for cc-collab CLI
#
# Installation:
#   Option 1: Source directly in ~/.bashrc
#     eval "$(_CC_COLLAB_COMPLETE=bash_source cc-collab)"
#
#   Option 2: Save to file and source
#     _CC_COLLAB_COMPLETE=bash_source cc-collab > ~/.cc-collab-complete.bash
#     source ~/.cc-collab-complete.bash
#
# This script is auto-generated from Click's completion system.
# For more info: https://click.palletsprojects.com/en/8.1.x/shell-completion/

_cc_collab_completion() {
    local IFS=$'\n'
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _CC_COLLAB_COMPLETE=bash_complete $1 ) )
    return 0
}

_cc_collab_completion_setup() {
    complete -o default -F _cc_collab_completion cc-collab
}

_cc_collab_completion_setup;
