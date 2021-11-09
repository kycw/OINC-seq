.PHONY: init
init:
	python3 -m venv .venv/pigpen

.PHONY: activate
activate:
	@echo 'source .venv/pigpen/bin/activate'
	@echo '# Usage'
	@echo '# eval $$(make activate)'
