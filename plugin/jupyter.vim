"=============================================================================
"     File: plugin/jupyter.vim
"  Created: 02/28/2018, 11:10
"   Author: Bernie Roesler
"
"  Description: Set up autocmds and config variables for jupyter-vim plugin
"
"  Filetypes: bash, java, javascript, julia, perl, python, ruby
"=============================================================================

if exists('g:loaded_jupyter_vim') || !(has('pythonx') || has('python') || has('python3')) || &compatible
    finish
endif

"-----------------------------------------------------------------------------
"        Configuration: {{{
"-----------------------------------------------------------------------------
let s:default_settings = {
    \ 'auto_connect': 0,
    \ 'cell_separators': "['##', '#%%', '# %%', '# <codecell>']",
    \ 'mapkeys': 1,
    \ 'monitor_console': 0,
    \ 'timer_intervals': '[300, 600, 1000, 1500, 3000, 10000]',
    \ 'verbose': 0
\ }

for [s:key, s:val] in items(s:default_settings)
    if !exists('g:jupyter_' . s:key)
        execute 'let g:jupyter_' . s:key . ' = ' . s:val
    endif
endfor

" Dict: &ft -> kernel_name
let s:language_dict = {
    \ 'sh': 'bash',
    \ 'c': 'cpp',
    \ 'cpp': 'cpp',
    \ 'java': 'java',
    \ 'javascript': 'javascript',
    \ 'julia': 'julia',
    \ 'perl': 'perl',
    \ 'perl6': 'raku',
    \ 'python': 'python',
    \ 'raku': 'raku',
    \ 'ruby': 'ruby',
    \ 'rust': 'rust',
    \ 'r': 'ir',
\ }

let s:language_string = join(keys(s:language_dict), ',')


augroup JupyterVimInit
    " By default, guess the kernel language based on the filetype. The user
    " can override this guess on a per-buffer basis.
    autocmd!
    autocmd FileType * let b:jupyter_kernel_type =
          \ get(s:language_dict, &filetype, 'none')

    execute 'autocmd FileType ' . s:language_string .
          \ ' call jupyter#load#MakeStandardCommands()'
    execute 'autocmd FileType ' . s:language_string .
          \ ' if g:jupyter_mapkeys | call jupyter#load#MapStandardKeys() | endif'
augroup END

"}}}----------------------------------------------------------------------------
"       Connect to Jupyter Kernel  {{{
"-------------------------------------------------------------------------------
if g:jupyter_auto_connect
    augroup JupyterConnect
        autocmd!
        autocmd BufReadPost * if -1 != index(keys(s:language_dict), &ft) |
              \ JupyterConnect *.json | endif
    augroup END
endif

let g:loaded_jupyter_vim = 1
"=============================================================================
"=============================================================================
