SHELL := /bin/bash

# Variables
build: draft=false

##@ Install
setup: ## Setup the Python virtual environment
	(cd src/build && python3 -m venv env);

install: setup ## Install the Python packages
	(cd src/build && source env/bin/activate && /usr/bin/env python3 -m pip install -r requirements.txt);

##@ Development
docker: ## Start the Docker containers
	docker-compose up

##@ Deployment
build: ## Build the website
	set -eu;
	rm -rf ./_build;
	(cd src/build && source env/bin/activate && /usr/bin/env python3 build.py --input=../../content --output=../../_build --draft=${draft});

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
