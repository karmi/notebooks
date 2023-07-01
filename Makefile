SHELL := /bin/bash

##@ Development
docker: ## Start the Docker containers
	docker-compose up

##@ Deployment
build: ## Build the website
	set -eu;
	(cd src/build && /usr/bin/env python3 build.py --input=../../content --output=../../_build);

preview: build ## Preview the website
	@bash -c ' \
		set -eu; \
		(python3 -m http.server -b localhost -d ./_build 8080) & PID=$$!; \
		trap "echo Exiting...; kill $$PID" SIGINT SIGTERM EXIT; \
		watchmedo shell-command --patterns="*.ipynb" --command="make build" ./content; \
	'

##@ Other
#------------------------------------------------------------------------------
help:  ## Display help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
#------------- <https://suva.sh/posts/well-documented-makefiles> --------------

.DEFAULT_GOAL := help
.PHONY: docker build preview
