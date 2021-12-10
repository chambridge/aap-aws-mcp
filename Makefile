
PYTHON=$(shell which python)
VERSION ?= 0.1.0
# Image URL to use all building/pushing image targets
IMG ?= quay.io/ansible/aap-mcp:v$(VERSION)

.PHONY: build

TOPDIR=$(shell pwd)
PYDIR=app

OS := $(shell uname)
ifeq ($(OS),Darwin)
	PREFIX	=
else
	PREFIX	= sudo
endif

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "--- Setup Commands ---"
	@echo "  build                                    build the docker image"
	@echo "      IMG=<quay.io image>                        @param - Required. The quay.io image name."


# Build the docker image
build:
	docker build -t ${IMG} .