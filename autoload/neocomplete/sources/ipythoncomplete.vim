if !has('python')
    finish
endif

let s:save_cpo = &cpo
set cpo&vim

let s:source = {
    \ 'name' : 'ipython-complete',
    \ 'kind' : 'keyword',
    \ 'mark' : '[IPy]',
    \ 'rank' : 4,
    \ }

function! neocomplete#sources#ipythoncomplete#complete(findstart, base)
    if &filetype == 'python'
        " Wrap in try statement in case IPython is not connected
        try
            return CompleteIPython(a:findstart, a:base)
        endtry
    endif
endfunction

function! s:source.gather_candidates(context)
    return neocomplete#sources#ipythoncomplete#complete(0, '')
endfunction

function! neocomplete#sources#ipythoncomplete#define()
    return s:source
endfunction

let &cpo = s:save_cpo
unlet s:save_cpo

