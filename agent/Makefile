# SuperBizAgent Python Makefile
# Automates project initialization, Docker management, and document vectorization

# ============================================================
# Configuration variables
# ============================================================
SERVER_URL = http://localhost:9900
UPLOAD_API = $(SERVER_URL)/api/upload
HEALTH_CHECK_API = $(SERVER_URL)/health
DOCS_DIR = aiops-docs
MILVUS_CONTAINER = milvus-standalone
PROMETHEUS_CONTAINER = showcase-prometheus
PROMETHEUS_URL = http://127.0.0.1:9090

# Color output
GREEN = \033[0;32m
YELLOW = \033[0;33m
RED = \033[0;31m
CYAN = \033[0;36m
NC = \033[0m

.PHONY: help init start stop restart check upload clean up down status wait \
        install install-dev dev run test test-quick format lint fix type-check \
        security pre-commit-install pre-commit check-all coverage docs shell \
        ipython watch add add-dev remove list-docs test-upload sync logs \
        start-cls stop-cls start-monitor stop-monitor start-prometheus stop-prometheus \
        status-prometheus start-api stop-api status-mcp

# ============================================================
# Default target: show help information
# ============================================================
help:
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  SuperBizAgent Python - Makefile Commands$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(CYAN)[One-step Operations]$(NC)"
	@echo "  $(YELLOW)make init$(NC)         - 🚀 one-step initialization (Docker -> services -> upload documents)"
	@echo ""
	@echo "$(CYAN)[Docker Management]$(NC)"
	@echo "  $(YELLOW)make up$(NC)           - 🐳 Start Milvus containers"
	@echo "  $(YELLOW)make down$(NC)         - 🛑 Stop Milvus containers"
	@echo "  $(YELLOW)make status$(NC)       - 📊 View container status"
	@echo "  $(YELLOW)make start-prometheus$(NC) - 📈 Start Prometheus showcase container"
	@echo "  $(YELLOW)make stop-prometheus$(NC)  - 🛑 Stop Prometheus showcase container"
	@echo "  $(YELLOW)make status-prometheus$(NC)- 📊 View Prometheus status"
	@echo ""
	@echo "$(CYAN)[Service Management]$(NC)"
	@echo "  $(YELLOW)make start$(NC)        - 🚀 Start all services (MCP + FastAPI)"
	@echo "  $(YELLOW)make stop$(NC)         - 🛑 Stop all services (MCP + FastAPI)"
	@echo "  $(YELLOW)make restart$(NC)      - 🔄 Restart all services"
	@echo "  $(YELLOW)make check$(NC)        - 🔍 Check FastAPI service status"
	@echo "  $(YELLOW)make status-mcp$(NC)   - 📊 View MCP service status"
	@echo ""
	@echo "$(CYAN)[MCP Service Management]$(NC)"
	@echo "  $(YELLOW)make start-cls$(NC)     - 📋 Start CLS MCP service"
	@echo "  $(YELLOW)make stop-cls$(NC)      - 🛑 Stop CLS MCP service"
	@echo "  $(YELLOW)make start-monitor$(NC) - 📊 Start Monitor MCP service"
	@echo "  $(YELLOW)make stop-monitor$(NC)  - 🛑 Stop Monitor MCP service"
	@echo "  $(YELLOW)make start-api$(NC)     - 🚀 Start FastAPI service"
	@echo "  $(YELLOW)make stop-api$(NC)      - 🛑 Stop FastAPI service"
	@echo ""
	@echo "$(CYAN)[Development Mode]$(NC)"
	@echo "  $(YELLOW)make dev$(NC)          - 🔧 Run in development mode (foreground, hot reload)"
	@echo "  $(YELLOW)make run$(NC)          - 🏭 Run in production mode (foreground)"
	@echo ""
	@echo "$(CYAN)[Document Management]$(NC)"
	@echo "  $(YELLOW)make upload$(NC)       - 📤 Upload docs documents in the directory"
	@echo "  $(YELLOW)make list-docs$(NC)    - 📚 List documents that can be uploaded"
	@echo "  $(YELLOW)make test-upload$(NC)  - 🧪 Test uploading a single file"
	@echo ""
	@echo "$(CYAN)[Dependency Management]$(NC)"
	@echo "  $(YELLOW)make install$(NC)      - 📦 Install production dependencies"
	@echo "  $(YELLOW)make install-dev$(NC)  - 📦 Install development dependencies"
	@echo "  $(YELLOW)make sync$(NC)         - 🔄 Sync dependencies"
	@echo "  $(YELLOW)make add PKG=xxx$(NC)  - ➕ Add a dependency package"
	@echo ""
	@echo "$(CYAN)[Code Quality]$(NC)"
	@echo "  $(YELLOW)make format$(NC)       - 🎨 Format code"
	@echo "  $(YELLOW)make lint$(NC)         - 🔍 Lint code"
	@echo "  $(YELLOW)make fix$(NC)          - 🔧 Auto-fix issues"
	@echo "  $(YELLOW)make test$(NC)         - 🧪 Run tests"
	@echo "  $(YELLOW)make check-all$(NC)    - ✅ Run all checks"
	@echo ""
	@echo "$(CYAN)[Other]$(NC)"
	@echo "  $(YELLOW)make clean$(NC)        - 🧹 Clean temporary files"
	@echo "  $(YELLOW)make shell$(NC)        - 🐍 Start Python Shell"
	@echo "  $(YELLOW)make coverage$(NC)     - 📊 View test coverage"
	@echo "  $(YELLOW)make logs$(NC)         - 📜 View service logs"
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)Usage examples:$(NC)"
	@echo "  1. one-step initialization: $(YELLOW)make init$(NC)"
	@echo "  2. Start services:   $(YELLOW)make start$(NC) (automatically starts Prometheus + MCP + FastAPI)"
	@echo "  3. Check status:   $(YELLOW)make status-mcp$(NC)"
	@echo "  4. Stop services:   $(YELLOW)make stop$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"

# ============================================================
# one-step initialization
# ============================================================
init:
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)🚀 Starting one-step SuperBizAgent initialization...$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)Step 1/4: Start Docker containers (Milvus vector database)$(NC)"
	@$(MAKE) up
	@echo ""
	@echo "$(YELLOW)Step 2/4: Start services (Prometheus + MCP + FastAPI)$(NC)"
	@$(MAKE) start
	@echo ""
	@echo "$(YELLOW)Step 3/4: Wait for services to become ready$(NC)"
	@$(MAKE) wait
	@echo ""
	@echo "$(YELLOW)Step 4/4: Upload documents to vector database$(NC)"
	@$(MAKE) upload
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)✅ Initialization complete. All documents were successfully vectorized and stored in the database$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(GREEN)🌐 Service URLs:$(NC)"
	@echo "   API service: $(SERVER_URL)"
	@echo "   API docs: $(SERVER_URL)/docs"
	@echo "   Attu (Milvus Web UI): http://localhost:8000"
	@echo "   MinIO: http://localhost:9001 (admin/minioadmin)"
	@echo ""
	@echo "$(YELLOW)💡 hint: Services are running in the background$(NC)"
	@echo "   View logs: $(YELLOW)tail -f server.log$(NC)"
	@echo "   Stop services: $(YELLOW)make stop$(NC)"

# ============================================================
# Docker Management
# ============================================================

# Start Docker containers with docker compose
up:
	@echo "$(YELLOW)🐳 Checking Docker container status...$(NC)"
	@if ! docker info > /dev/null 2>&1; then \
		echo "$(YELLOW)⚠️  Docker is not running; trying to start Colima...$(NC)"; \
		colima start 2>/dev/null || (echo "$(RED)❌ Unable to start Docker; please start it manually$(NC)" && exit 1); \
		sleep 3; \
	fi
	@if docker ps --format '{{.Names}}' | grep -q "^$(MILVUS_CONTAINER)$$"; then \
		echo "$(GREEN)✅ Milvus containers are already running$(NC)"; \
		docker ps --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10; \
	else \
		echo "$(YELLOW)🚀 Starting Milvus-related containers...$(NC)"; \
		docker compose -f vector-database.yml up -d; \
		echo "$(YELLOW)⏳ Waiting for containers to start...$(NC)"; \
		sleep 5; \
		if docker ps --format '{{.Names}}' | grep -q "^$(MILVUS_CONTAINER)$$"; then \
			echo "$(GREEN)✅ Docker containers started successfully!$(NC)"; \
			echo ""; \
			echo "$(GREEN)📋 Running containers:$(NC)"; \
			docker ps --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10; \
			echo ""; \
			echo "$(GREEN)🌐 Service URLs:$(NC)"; \
			echo "   Milvus: localhost:19530"; \
			echo "   Attu (Web UI): http://localhost:8000"; \
			echo "   MinIO: http://localhost:9001 (admin/minioadmin)"; \
		else \
			echo "$(RED)❌ Container startup failed$(NC)"; \
			exit 1; \
		fi; \
	fi

# Stop Docker containers
down:
	@echo "$(YELLOW)🛑 Stop Docker containers...$(NC)"
	@if docker ps --format '{{.Names}}' | grep -q "milvus"; then \
		docker compose -f vector-database.yml down; \
		echo "$(GREEN)✅ Docker containers stopped$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  No running Milvus containers$(NC)"; \
	fi

# View container status
status:
	@echo "$(YELLOW)📊 Docker container status:$(NC)"
	@echo ""
	@if docker ps -a --format '{{.Names}}' | grep -q "milvus"; then \
		docker ps -a --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"; \
		echo ""; \
		running=$$(docker ps --filter "name=milvus" --format '{{.Names}}' | wc -l | tr -d ' '); \
		total=$$(docker ps -a --filter "name=milvus" --format '{{.Names}}' | wc -l | tr -d ' '); \
		echo "$(GREEN)running: $$running / $$total$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  No Milvus-related containers found$(NC)"; \
		echo "$(YELLOW)hint: Please create Milvus containers first$(NC)"; \
	fi

# Start Prometheus showcase container
start-prometheus:
	@echo "$(YELLOW)📈 Start Prometheus showcase container...$(NC)"
	@if ! docker info > /dev/null 2>&1; then \
		echo "$(YELLOW)⚠️  Docker is not running; trying to start Colima...$(NC)"; \
		colima start 2>/dev/null || (echo "$(RED)❌ Unable to start Docker; please start it manually$(NC)" && exit 1); \
		sleep 3; \
	fi
	@if docker ps --format '{{.Names}}' | grep -q "^$(PROMETHEUS_CONTAINER)$$"; then \
		echo "$(GREEN)✅ Prometheus is already running ($(PROMETHEUS_URL))$(NC)"; \
	elif docker ps -a --format '{{.Names}}' | grep -q "^$(PROMETHEUS_CONTAINER)$$"; then \
		echo "$(YELLOW)📦 Starting the existing Prometheus container...$(NC)"; \
		docker start $(PROMETHEUS_CONTAINER) > /dev/null; \
		echo "$(GREEN)✅ Prometheus started successfully$(NC)"; \
		echo "$(YELLOW)   URL: $(PROMETHEUS_URL)$(NC)"; \
		echo "$(YELLOW)   Alerts API: $(PROMETHEUS_URL)/api/v1/alerts$(NC)"; \
	else \
		echo "$(YELLOW)📦 Creating Prometheus showcase container with demo firing alert...$(NC)"; \
		docker run -d \
			--name $(PROMETHEUS_CONTAINER) \
			-p 9090:9090 \
			-v "$$(pwd)/prometheus-demo/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
			-v "$$(pwd)/prometheus-demo/alerts.yml:/etc/prometheus/alerts.yml:ro" \
			prom/prometheus:latest > /dev/null; \
		sleep 3; \
		if curl -s -f "$(PROMETHEUS_URL)/-/ready" > /dev/null 2>&1; then \
			echo "$(GREEN)✅ Prometheus started successfully$(NC)"; \
			echo "$(YELLOW)   URL: $(PROMETHEUS_URL)$(NC)"; \
			echo "$(YELLOW)   Alerts API: $(PROMETHEUS_URL)/api/v1/alerts$(NC)"; \
		else \
			echo "$(RED)❌ Prometheus was not ready after startup; please check: docker logs $(PROMETHEUS_CONTAINER)$(NC)"; \
			exit 1; \
		fi; \
	fi

# Stop Prometheus showcase container
stop-prometheus:
	@echo "$(YELLOW)🛑 Stop Prometheus showcase container...$(NC)"
	@if docker ps --format '{{.Names}}' | grep -q "^$(PROMETHEUS_CONTAINER)$$"; then \
		docker stop $(PROMETHEUS_CONTAINER) > /dev/null; \
		echo "$(GREEN)✅ Prometheus stopped$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  Prometheus container is not running$(NC)"; \
	fi

# View Prometheus status
status-prometheus:
	@echo "$(YELLOW)📊 Prometheus status:$(NC)"
	@if docker ps -a --format '{{.Names}}' | grep -q "^$(PROMETHEUS_CONTAINER)$$"; then \
		docker ps -a --filter "name=$(PROMETHEUS_CONTAINER)" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"; \
		curl -s -f "$(PROMETHEUS_URL)/-/ready" > /dev/null 2>&1 && \
			echo "Connection: $(GREEN)✅ OK ($(PROMETHEUS_URL))$(NC)" || \
			echo "Connection: $(RED)❌ cannot connect ($(PROMETHEUS_URL))$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  No Prometheus container found$(NC)"; \
	fi

# ============================================================
# MCP Service Management
# ============================================================

# Start CLS MCP service
start-cls:
	@echo "$(YELLOW)📋 Start CLS MCP service...$(NC)"
	@if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then \
		echo "$(GREEN)✅ CLS MCP service is already running$(NC)"; \
	else \
		echo "$(YELLOW)📦 Starting CLS MCP service in the background...$(NC)"; \
		nohup .venv/bin/python mcp_servers/cls_server.py > mcp_cls.log 2>&1 & \
		echo $$! > mcp_cls.pid; \
		sleep 2; \
		if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then \
			echo "$(GREEN)✅ CLS MCP service started successfully$(NC)"; \
			echo "$(YELLOW)   PID: $$(cat mcp_cls.pid)$(NC)"; \
			echo "$(YELLOW)   URL: http://127.0.0.1:8003/mcp$(NC)"; \
			echo "$(YELLOW)   logs: mcp_cls.log$(NC)"; \
		else \
			echo "$(RED)❌ CLS MCP service startup failed$(NC)"; \
			echo "$(YELLOW)Please check logs: tail -f mcp_cls.log$(NC)"; \
		fi; \
	fi

# Start Monitor MCP service
start-monitor:
	@echo "$(YELLOW)📊 Start Monitor MCP service...$(NC)"
	@if pgrep -f "mcp_servers/monitor_server.py" > /dev/null 2>&1; then \
		echo "$(GREEN)✅ Monitor MCP service is already running$(NC)"; \
	else \
		echo "$(YELLOW)📦 Starting Monitor MCP service in the background...$(NC)"; \
		nohup .venv/bin/python mcp_servers/monitor_server.py > mcp_monitor.log 2>&1 & \
		echo $$! > mcp_monitor.pid; \
		sleep 2; \
		if pgrep -f "mcp_servers/monitor_server.py" > /dev/null 2>&1; then \
			echo "$(GREEN)✅ Monitor MCP service started successfully$(NC)"; \
			echo "$(YELLOW)   PID: $$(cat mcp_monitor.pid)$(NC)"; \
			echo "$(YELLOW)   URL: http://127.0.0.1:8004/mcp$(NC)"; \
			echo "$(YELLOW)   logs: mcp_monitor.log$(NC)"; \
		else \
			echo "$(RED)❌ Monitor MCP service startup failed$(NC)"; \
			echo "$(YELLOW)Please check logs: tail -f mcp_monitor.log$(NC)"; \
		fi; \
	fi

# Stop Monitor MCP service
stop-monitor:
	@echo "$(YELLOW)🛑 Stop Monitor MCP service...$(NC)"
	@if [ -f mcp_monitor.pid ]; then \
		pid=$$(cat mcp_monitor.pid); \
		if ps -p $$pid > /dev/null 2>&1; then \
			kill $$pid; \
			echo "$(GREEN)✅ Monitor MCP service stopped (PID: $$pid)$(NC)"; \
		else \
			echo "$(YELLOW)⚠️  Process does not exist (PID: $$pid)$(NC)"; \
		fi; \
		rm -f mcp_monitor.pid; \
	else \
		echo "$(YELLOW)⚠️  mcp_monitor.pid file not found$(NC)"; \
		pkill -f "mcp_servers/monitor_server.py" 2>/dev/null && \
			echo "$(GREEN)✅ Stopped all Monitor MCP processes$(NC)" || \
			echo "$(YELLOW)⚠️  No running Monitor MCP processes$(NC)"; \
	fi

# Check MCP service status
status-mcp:
	@echo "$(YELLOW)📊 MCP service status:$(NC)"
	@echo ""
	@echo "$(CYAN)CLS MCP service:$(NC)"
	@if pgrep -f "mcp_servers/cls_server.py" > /dev/null 2>&1; then \
		pid=$$(pgrep -f "mcp_servers/cls_server.py"); \
		echo "  Status: $(GREEN)running$(NC)"; \
		echo "  PID: $$pid"; \
		echo "  URL: http://127.0.0.1:8003/mcp"; \
		curl -s http://127.0.0.1:8003/mcp > /dev/null 2>&1 && \
			echo "  Connection: $(GREEN)✅ OK$(NC)" || \
			echo "  Connection: $(RED)❌ cannot connect$(NC)"; \
	else \
		echo "  Status: $(RED)not running$(NC)"; \
	fi
	@echo ""
	@echo "$(CYAN)Monitor MCP service:$(NC)"
	@if pgrep -f "mcp_servers/monitor_server.py" > /dev/null 2>&1; then \
		pid=$$(pgrep -f "mcp_servers/monitor_server.py"); \
		echo "  Status: $(GREEN)running$(NC)"; \
		echo "  PID: $$pid"; \
		echo "  URL: http://127.0.0.1:8004/mcp"; \
		curl -s http://127.0.0.1:8004/mcp > /dev/null 2>&1 && \
			echo "  Connection: $(GREEN)✅ OK$(NC)" || \
			echo "  Connection: $(RED)❌ cannot connect$(NC)"; \
	else \
		echo "  Status: $(RED)not running$(NC)"; \
	fi
	@echo ""
	@echo "$(CYAN)Math MCP service:$(NC)"
	@echo "  Status: $(YELLOW)removed (sample service)$(NC)"

# ============================================================
# FastAPI Service Management
# ============================================================

# Start all services (MCP + FastAPI)
start:
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)🚀 Start all services$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo ""
	@$(MAKE) start-cls
	@sleep 1
	@echo ""
	@$(MAKE) start-monitor
	@sleep 1
	@echo ""
	@$(MAKE) start-prometheus
	@sleep 1
	@echo ""
	@$(MAKE) start-api
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)✅ All services started!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"

# Start FastAPI service
start-api:
	@echo "$(YELLOW)🚀 Start FastAPI service...$(NC)"
	@if curl -s -f $(HEALTH_CHECK_API) > /dev/null 2>&1; then \
		echo "$(GREEN)✅ FastAPI service is already running ($(SERVER_URL))$(NC)"; \
	else \
		echo "$(YELLOW)📦 Starting FastAPI service in the background...$(NC)"; \
		nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 9900 > server.log 2>&1 & \
		echo $$! > server.pid; \
		echo "$(GREEN)✅ FastAPI service start command executed$(NC)"; \
		echo "$(YELLOW)   PID: $$(cat server.pid)$(NC)"; \
		echo "$(YELLOW)   URL: $(SERVER_URL)$(NC)"; \
		echo "$(YELLOW)   logs: server.log$(NC)"; \
	fi

# Stop all services (FastAPI + MCP)
stop:
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)🛑 Stop all services$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo ""
	@$(MAKE) stop-api
	@echo ""
	@$(MAKE) stop-cls
	@echo ""
	@$(MAKE) stop-monitor
	@echo ""
	@$(MAKE) stop-prometheus
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)✅ All services stopped!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"

# Stop CLS MCP service
stop-cls:
	@echo "$(YELLOW)🛑 Stop CLS MCP service...$(NC)"
	@if [ -f mcp_cls.pid ]; then \
		pid=$$(cat mcp_cls.pid); \
		if ps -p $$pid > /dev/null 2>&1; then \
			kill $$pid; \
			echo "$(GREEN)✅ CLS MCP service stopped (PID: $$pid)$(NC)"; \
		else \
			echo "$(YELLOW)⚠️  Process does not exist (PID: $$pid)$(NC)"; \
		fi; \
		rm -f mcp_cls.pid; \
	else \
		echo "$(YELLOW)⚠️  mcp_cls.pid file not found$(NC)"; \
		pkill -f "mcp_servers/cls_server.py" 2>/dev/null && \
			echo "$(GREEN)✅ Stopped all CLS MCP processes$(NC)" || \
			echo "$(YELLOW)⚠️  No running CLS MCP processes$(NC)"; \
	fi

# Stop FastAPI service
stop-api:
	@echo "$(YELLOW)🛑 Stop FastAPI service...$(NC)"
	@if [ -f server.pid ]; then \
		pid=$$(cat server.pid); \
		if ps -p $$pid > /dev/null 2>&1; then \
			kill $$pid; \
			echo "$(GREEN)✅ FastAPI service stopped (PID: $$pid)$(NC)"; \
		else \
			echo "$(YELLOW)⚠️  Process does not exist (PID: $$pid)$(NC)"; \
		fi; \
		rm -f server.pid; \
	else \
		echo "$(YELLOW)⚠️  server.pid file not found$(NC)"; \
		pkill -f "uvicorn app.main:app" 2>/dev/null && \
			echo "$(GREEN)✅ Stopped all uvicorn processes$(NC)" || \
			echo "$(YELLOW)⚠️  No running uvicorn processes$(NC)"; \
	fi

# Restart all services
restart:
	@echo "$(YELLOW)🔄 Restart all services...$(NC)"
	@echo ""
	@$(MAKE) stop
	@sleep 2
	@$(MAKE) start
	@$(MAKE) wait
	@echo ""
	@echo "$(GREEN)✅ All services restarted!$(NC)"

# Wait for services to become ready (up to 60 seconds)
wait:
	@echo "$(YELLOW)⏳ Waiting for the server to become ready...$(NC)"
	@max_attempts=60; \
	attempt=0; \
	while [ $$attempt -lt $$max_attempts ]; do \
		if curl -s -f $(HEALTH_CHECK_API) > /dev/null 2>&1; then \
			echo ""; \
			echo "$(GREEN)✅ Server is ready! ($(SERVER_URL))$(NC)"; \
			exit 0; \
		fi; \
		attempt=$$((attempt + 1)); \
		printf "\r$(YELLOW)   Waiting... [$$attempt/$$max_attempts]$(NC)"; \
		sleep 1; \
	done; \
	echo ""; \
	echo "$(RED)❌ Server startup timed out!$(NC)"; \
	echo "$(YELLOW)Please check logs: tail -f server.log$(NC)"; \
	exit 1

# Check service status
check:
	@echo "$(YELLOW)🔍 Checking server status...$(NC)"
	@if curl -s -f $(HEALTH_CHECK_API) > /dev/null 2>&1; then \
		echo "$(GREEN)✅ Server is running normally ($(SERVER_URL))$(NC)"; \
		echo ""; \
		echo "$(CYAN)Health check response:$(NC)"; \
		curl -s $(HEALTH_CHECK_API) | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False))" 2>/dev/null || curl -s $(HEALTH_CHECK_API); \
	else \
		echo "$(RED)❌ Server is not running or cannot be reached!$(NC)"; \
		echo "$(YELLOW)Please start services first: make start$(NC)"; \
		exit 1; \
	fi

# Run in development mode (foreground, hot reload)
dev:
	@echo "$(YELLOW)🔧 Starting development server (hot reload)...$(NC)"
	.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 9900

# Run in production mode (foreground)
run:
	@echo "$(YELLOW)🏭 Starting production server...$(NC)"
	.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 9900

# ============================================================
# Document Management
# ============================================================

# Upload all documents
upload:
	@echo "$(YELLOW)📤 Starting upload for $(DOCS_DIR) documents in the directory...$(NC)"
	@if [ ! -d "$(DOCS_DIR)" ]; then \
		echo "$(RED)❌ Directory $(DOCS_DIR) does not exist!$(NC)"; \
		exit 1; \
	fi
	@count=0; \
	success=0; \
	failed=0; \
	for file in $(DOCS_DIR)/*.md; do \
		if [ -f "$$file" ]; then \
			count=$$((count + 1)); \
			filename=$$(basename "$$file"); \
			echo "$(YELLOW)  [$$count] Uploading file: $$filename$(NC)"; \
			response=$$(curl -s -w "\n%{http_code}" -X POST $(UPLOAD_API) \
				-F "file=@$$file" \
				-H "Accept: application/json"); \
			http_code=$$(echo "$$response" | tail -n1); \
			body=$$(echo "$$response" | sed '$$d'); \
			if [ "$$http_code" = "200" ]; then \
				echo "$(GREEN)      ✅ success: $$filename$(NC)"; \
				success=$$((success + 1)); \
			else \
				echo "$(RED)      ❌ failed: $$filename (HTTP $$http_code)$(NC)"; \
				echo "$$body" | head -n 3; \
				failed=$$((failed + 1)); \
			fi; \
			sleep 1; \
		fi; \
	done; \
	echo ""; \
	echo "$(GREEN)📊 Upload statistics:$(NC)"; \
	echo "   total: $$count files"; \
	echo "   $(GREEN)success: $$success$(NC)"; \
	if [ $$failed -gt 0 ]; then \
		echo "   $(RED)failed: $$failed$(NC)"; \
	fi

# List documents
list-docs:
	@echo "$(YELLOW)📚 $(DOCS_DIR) documents in the directory:$(NC)"
	@if [ -d "$(DOCS_DIR)" ]; then \
		ls -lh $(DOCS_DIR)/*.md 2>/dev/null || echo "$(RED)No .md files found$(NC)"; \
	else \
		echo "$(RED)Directory $(DOCS_DIR) does not exist$(NC)"; \
	fi

# Test uploading a single file
test-upload:
	@echo "$(YELLOW)🧪 Test uploading a single file...$(NC)"
	@first_file=$$(ls $(DOCS_DIR)/*.md 2>/dev/null | head -n1); \
	if [ -n "$$first_file" ]; then \
		echo "$(YELLOW)Uploading file: $$first_file$(NC)"; \
		curl -X POST $(UPLOAD_API) \
			-F "file=@$$first_file" \
			-H "Accept: application/json" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False))" 2>/dev/null || \
			curl -X POST $(UPLOAD_API) -F "file=@$$first_file"; \
	else \
		echo "$(RED)Test file does not exist$(NC)"; \
	fi

# ============================================================
# Dependency Management
# ============================================================

install:  ## Install dependencies (production)
	@echo "$(YELLOW)📦 Install dependencies...$(NC)"
	pip install -r requirements.txt 2>/dev/null || pip install -e .
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

install-dev:  ## Install development dependencies
	@echo "$(YELLOW)📦 Install development dependencies...$(NC)"
	pip install -e ".[dev]" 2>/dev/null || pip install -e .
	@echo "$(GREEN)✅ Development dependencies installed$(NC)"

sync:  ## Sync dependencies
	@echo "$(YELLOW)🔄 Sync dependencies...$(NC)"
	pip install -e . --upgrade
	@echo "$(GREEN)✅ Dependencies synced$(NC)"

add:  ## Add a dependency package (Usage: make add PKG=package_name)
	@echo "$(YELLOW)📦 Add dependency: $(PKG)...$(NC)"
	pip install $(PKG)

add-dev:  ## Add a development dependency (Usage: make add-dev PKG=package_name)
	@echo "$(YELLOW)📦 Add a development dependency: $(PKG)...$(NC)"
	pip install $(PKG)

remove:  ## Remove a dependency package (Usage: make remove PKG=package_name)
	@echo "$(YELLOW)🗑️  Remove dependency: $(PKG)...$(NC)"
	pip uninstall $(PKG)

# ============================================================
# Code Quality
# ============================================================

format:  ## Format code
	@echo "$(YELLOW)🎨 Format code...$(NC)"
	python3 -m ruff check --select I --fix app/ 2>/dev/null || true
	python3 -m ruff format app/ 2>/dev/null || python3 -m black app/
	@echo "$(GREEN)✅ Formatting complete$(NC)"

lint:  ## Lint code
	@echo "$(YELLOW)🔍 Lint code...$(NC)"
	python3 -m ruff check app/ 2>/dev/null || python3 -m flake8 app/
	@echo "$(GREEN)✅ Check complete$(NC)"

fix:  ## Auto-fix code issues
	@echo "$(YELLOW)🔧 Auto-fix code issues...$(NC)"
	python3 -m ruff check --fix app/ 2>/dev/null || true
	python3 -m ruff format app/ 2>/dev/null || python3 -m black app/
	@echo "$(GREEN)✅ Fix complete$(NC)"

type-check:  ## Type check
	@echo "$(YELLOW)🔍 Type check...$(NC)"
	python3 -m mypy app/ --ignore-missing-imports
	@echo "$(GREEN)✅ Type check complete$(NC)"

security:  ## Security check
	@echo "$(YELLOW)🔒 Security check...$(NC)"
	python3 -m bandit -r app/ -ll
	@echo "$(GREEN)✅ Security check complete$(NC)"

test:  ## Run tests
	@echo "$(YELLOW)🧪 Run tests...$(NC)"
	python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-quick:  ## Quick tests
	@echo "$(YELLOW)⚡ Quick tests...$(NC)"
	python3 -m pytest tests/ -v

check-all:  ## Run all checks
	@echo "$(YELLOW)🚀 Run all checks...$(NC)"
	@$(MAKE) format
	@$(MAKE) lint
	@$(MAKE) test
	@echo "$(GREEN)✅ All checks passed!$(NC)"

pre-commit-install:  ## Install pre-commit hooks
	@echo "$(YELLOW)🔗 Install pre-commit hooks...$(NC)"
	python3 -m pre_commit install
	python3 -m pre_commit install --hook-type commit-msg
	@echo "$(GREEN)✅ Pre-commit hooks installed$(NC)"

pre-commit:  ## Run pre-commit checks
	@echo "$(YELLOW)🔍 Run pre-commit checks...$(NC)"
	python3 -m pre_commit run --all-files

coverage:  ## View test coverage report
	@echo "$(YELLOW)📊 Generating coverage report...$(NC)"
	python3 -m pytest tests/ --cov=app --cov-report=html --cov-report=term
	@echo "$(GREEN)✅ Coverage report generated: htmlcov/index.html$(NC)"
	@open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Please open manually htmlcov/index.html"

# ============================================================
# Other Tools
# ============================================================

clean:  ## Clean temporary files
	@echo "$(YELLOW)🧹 Clean temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage
	rm -f server.pid server.log
	rm -f mcp_cls.pid mcp_cls.log
	rm -f mcp_monitor.pid mcp_monitor.log
	rm -rf uploads/*.tmp 2>/dev/null || true
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

shell:  ## Start Python shell
	@echo "$(YELLOW)🐍 Start Python shell...$(NC)"
	python3 -i -c "import sys; sys.path.insert(0, '.'); from app.config import config; print('Environment loaded; config object is available')"

ipython:  ## Start IPython shell
	@echo "$(YELLOW)🐍 Start IPython shell...$(NC)"
	python3 -m IPython

docs:  ## Open API docs
	@echo "$(YELLOW)📚 API docs URL: $(SERVER_URL)/docs$(NC)"
	@open $(SERVER_URL)/docs 2>/dev/null || xdg-open $(SERVER_URL)/docs 2>/dev/null || echo "Please open manually $(SERVER_URL)/docs"

watch:  ## Watch file changes and automatically run tests
	@echo "$(YELLOW)👀 Watching file changes...$(NC)"
	python3 -m pytest_watch -- -v

logs:  ## View service logs
	@echo "$(YELLOW)📜 View service logs...$(NC)"
	@if [ -f server.log ]; then \
		tail -f server.log; \
	else \
		echo "$(RED)Log file does not exist$(NC)"; \
		echo "$(YELLOW)hint: Logs are generated after starting services with make start$(NC)"; \
	fi
