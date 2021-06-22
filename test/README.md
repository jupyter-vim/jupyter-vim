Tests must be made with docker command in jupyter-vim root directory

jupyter-vim <- testbed/vim:latest <- alpine:3.12: A minimal Docker image based on Alpine Linux with a complete package index and only 5 MB in size!

```bash
# Build image
docker build --tag  jupyter-vim .

# Run tests
docker run -it --rm -v $PWD/:/testplugin jupyter-vim /vim-build/bin/vim_8.1.0519 -i NONE -N -u /testplugin/test/vimrc -Es '+Vader! /testplugin/test/*.vader'
```

* -v Bind volume: repodir -> /testing
* -i No viminfo
* -N No compatible
* -u  Vimrc
* -Es Execute mode, non interactive

The docker image aims to provide:
1. Vim with python3 support
2. Jupyter (with libzmq well installed)
