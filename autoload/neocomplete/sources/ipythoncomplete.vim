let s:save_cpo = &cpo
set cpo&vim

let s:source = {
    \ 'name' : 'ipython-complete',
    \ 'kind' : 'keyword',
    \ 'mark' : '[IPy]',
    \ 'rank' : 4,
    \ }

function! neocomplete#sources#ipythoncomplete(findstart, base)
    if !exists('*CompleteIPython')
        return
    else
        return CompleteIPython(a:findstart, a:base)
    endif
endfunction

function! s:source.gather_candidates(context)
    return neocomplete#sources#ipythoncomplete(0, '')
endfunction

function! neocomplete#sources#tmuxcomplete#define()
    return s:source
endfunction

let &cpo = s:save_cpo
unlet s:save_cpo

