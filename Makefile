.PHONY: up-inference down-inference logs-inference ping-inference

up-inference:
	docker compose up -d --build inference

down-inference:
	docker compose down

logs-inference:
	docker compose logs -f inference

ping-inference:
	curl http://localhost:8080/ping
