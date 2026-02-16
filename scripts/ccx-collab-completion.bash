#!/bin/bash
# Bash completion for ccx-collab CLI
#
# Installation:
#   Option 1: Source directly in ~/.bashrc
#     eval "$(_CCX_COLLAB_COMPLETE=bash_source ccx-collab)"
#
#   Option 2: Save to file and source
#     _CCX_COLLAB_COMPLETE=bash_source ccx-collab > ~/.ccx-collab-complete.bash
#     source ~/.ccx-collab-complete.bash
#
# This script is auto-generated from Click's completion system.
# For more info: https://click.palletsprojects.com/en/8.1.x/shell-completion/

_ccx_collab_completion() {
    local IFS=$'\n'
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _CCX_COLLAB_COMPLETE=bash_complete $1 ) )
    return 0
}

_ccx_collab_completion_setup() {
    complete -o default -F _ccx_collab_completion ccx-collab
}

_ccx_collab_completion_setup;
