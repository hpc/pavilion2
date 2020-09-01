set hlsearch

set t_kb=


set ai
set si
inoremap # X#
set nocompatible
set tabstop=4
set shiftwidth=4
set smarttab
set softtabstop=4
set expandtab
set backspace=indent,eol,start
set gfn=Monospace\ 8
syntax on
set whichwrap=<,>
set foldmethod=marker
set wildmenu
set title
set ruler
set showmatch
set showcmd
set pastetoggle=<F12> 
colorscheme darkblue

set pdev=pdf
set printoptions=paper:letter,syntax:y,wrap:y

set textwidth=100

autocmd BufEnter [Mm]akefile*,*.mak,*.make set noexpandtab textwidth=0 sw=4
autocmd BufLeave [Mm]akefile*,*.mak,*.make set expandtab textwidth=100 

autocmd BufNewFile,BufRead *.wsgi set filetype=python
autocmd BufNewFile,BufRead *.mako set filetype=mako
autocmd BufReadPre,BufNewFile *.go set filetype=go fileencoding=utf-8 fileencodings=utf-8 textwidth=100
autocmd BufRead,BufNewFile *.tex set textwidth=60
