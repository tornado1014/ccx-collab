#compdef cc-collab
# Zsh completion for cc-collab CLI
#
# Installation:
#   Option 1: Source directly in ~/.zshrc
#     eval "$(_CC_COLLAB_COMPLETE=zsh_source cc-collab)"
#
#   Option 2: Save to file and source
#     _CC_COLLAB_COMPLETE=zsh_source cc-collab > ~/.cc-collab-complete.zsh
#     source ~/.cc-collab-complete.zsh
#
# This script is auto-generated from Click's completion system.
# For more info: https://click.palletsprojects.com/en/8.1.x/shell-completion/

_cc_collab_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[cc-collab] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _CC_COLLAB_COMPLETE=zsh_complete cc-collab)}")

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
    _cc_collab_completion "$@"
else
    # eval
    compdef _cc_collab_completion cc-collab
fi
