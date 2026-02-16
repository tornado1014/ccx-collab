#compdef ccx-collab
# Zsh completion for ccx-collab CLI
#
# Installation:
#   Option 1: Source directly in ~/.zshrc
#     eval "$(_CCX_COLLAB_COMPLETE=zsh_source ccx-collab)"
#
#   Option 2: Save to file and source
#     _CCX_COLLAB_COMPLETE=zsh_source ccx-collab > ~/.ccx-collab-complete.zsh
#     source ~/.ccx-collab-complete.zsh
#
# This script is auto-generated from Click's completion system.
# For more info: https://click.palletsprojects.com/en/8.1.x/shell-completion/

_ccx_collab_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[ccx-collab] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _CCX_COLLAB_COMPLETE=zsh_complete ccx-collab)}")

    for key descr in ${(kv)response}; do
        if [[ "$descr" == "_" ]]; then
            completions+=("$key")
        else
            completions_with_descriptions+=("$key":"$descr")
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

if [[ $zsh_eval_context[-1] == loadautofun ]]; then
    # autoload from fpath
    _ccx_collab_completion "$@"
else
    # eval
    compdef _ccx_collab_completion ccx-collab
fi
