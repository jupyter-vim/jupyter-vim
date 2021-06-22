FROM testbed/vim:latest

# Add packages
RUN apk --no-cache update
RUN apk --no-cache --update add gcc build-base autoconf coreutils
RUN apk --no-cache --update add libffi-dev libzmq libzmq zeromq-dev zeromq freetype libpng libjpeg-turbo freetype-dev libpng-dev libjpeg-turbo-dev
RUN apk --no-cache --update add bash git
RUN apk --no-cache --update add python3 py3-pip python3-dev

## Get vint for linting
RUN pip3 install vim-vint
RUN pip3 install pylint
RUN pip3 install wheel
RUN pip3 install pyzmq
RUN pip3 install jupyter
RUN pip3 install jupyter-console

# Get vader for unit tests
RUN git clone -n https://github.com/junegunn/vader.vim /vader
WORKDIR /vader
RUN git checkout de8a976f1eae2c2b680604205c3e8b5c8882493c

# Build vim and neovim versions we want to test
WORKDIR /
# for cache deletion
RUN install_vim -tag v8.0.0027 -py -py3 -name vim_8.0.0027 -build \
                -tag v8.1.0519 -py -py3 -name vim_8.1.0519 -build \
                -tag neovim:v0.3.8 -py -py3 -name nvim_0.3.8 -build
