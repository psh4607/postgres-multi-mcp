# Postgres Multi-MCP

A PostgreSQL MCP server that supports **multiple database connections** from a single instance. Based on [postgres-mcp](https://github.com/crystaldba/postgres-mcp), this fork adds the ability to manage multiple databases through a YAML configuration file.

## Features

- **Multiple Database Support**: Connect to multiple PostgreSQL databases from a single MCP server
- **YAML Configuration**: Define all your database connections in a simple YAML file
- **Per-Database Access Modes**: Configure each database with `unrestricted` (read/write) or `restricted` (read-only) access
- **Hot Reload**: Reload database configurations without restarting the server
- **All Original Features**: Index tuning, explain plans, health checks, and safe SQL execution

## Quick Start

### 1. Create Configuration File

Create a `databases.yaml` file in one of these locations (searched in order):

1. `~/.cursor/databases.yaml` - User-level config (shared across all projects)
2. `.cursor/databases.yaml` - Project-level config
3. `./databases.yaml` - Current directory (for Docker)

```yaml
databases:
  - name: local-db
    description: Local development database
    uri: postgresql://user:password@localhost:5432/myapp_dev
    access_mode: unrestricted

  - name: prod-db
    description: Production database (read-only)
    uri: postgresql://user:password@prod-host:5432/myapp_prod
    access_mode: restricted
```

### 2. Run with Docker (Recommended)

```bash
# Pull the image (or build locally)
docker build -t postgres-multi-mcp .

# Run with SSE transport
docker run -p 8000:8000 \
  -v ./databases.yaml:/app/databases.yaml:ro \
  postgres-multi-mcp

# Or use docker-compose
docker-compose up -d
```

### 3. Configure Your MCP Client

For Cursor, add to your MCP settings:

```json
{
  "mcpServers": {
    "postgres-multi": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## Available Tools

All tools now include a `database_name` parameter to specify which database to query:

| Tool                       | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| `list_databases`           | List all configured databases with connection status |
| `reload_database_config`   | Hot-reload database configurations from YAML         |
| `list_schemas`             | List all schemas in the specified database           |
| `list_objects`             | List tables, views, sequences, or extensions         |
| `get_object_details`       | Get detailed information about a database object     |
| `execute_sql`              | Execute SQL (respects access_mode setting)           |
| `explain_query`            | Get execution plan for a query                       |
| `analyze_workload_indexes` | Analyze workload and recommend indexes               |
| `analyze_query_indexes`    | Analyze specific queries for index recommendations   |
| `analyze_db_health`        | Comprehensive database health checks                 |
| `get_top_queries`          | Get slowest or most resource-intensive queries       |

## Configuration

### databases.yaml

```yaml
databases:
  - name: string # Required: Unique identifier for the database
    description: string # Optional: Human-readable description
    uri: string # Required: PostgreSQL connection URI
    access_mode: string # Optional: 'unrestricted' or 'restricted' (default: restricted)
```

### Access Modes

- **unrestricted**: Full read/write access. Use for development environments.
- **restricted**: Read-only mode with 30-second timeout. Use for production databases.

### Configuration File Search Order

1. `DATABASES_CONFIG_PATH` environment variable (if set)
2. `~/.cursor/databases.yaml` (user-level)
3. `.cursor/databases.yaml` (project-level)
4. `./databases.yaml` (current directory)

### Environment Variables

| Variable                | Default                  | Description                               |
| ----------------------- | ------------------------ | ----------------------------------------- |
| `DATABASES_CONFIG_PATH` | (see search order above) | Path to the configuration file            |
| `LOG_LEVEL`             | `INFO`                   | Logging level                             |
| `OPENAI_API_KEY`        | -                        | Required for LLM-based index optimization |

## Usage Examples

### List Available Databases

Ask your AI assistant:

> "What databases are available?"

### Query a Specific Database

> "Show me all tables in the local-db database"

### Check Database Health

> "Check the health of the prod-db database"

### Compare Schemas

> "Compare the user tables between local-db and prod-db"

## Running Without Docker

```bash
# Install dependencies
uv pip install -e .

# Run with stdio transport
postgres-mcp --config databases.yaml

# Run with SSE transport
postgres-mcp --config databases.yaml --transport sse --sse-host 0.0.0.0 --sse-port 8000
```

## Development

```bash
# Clone the repository
git clone https://github.com/psh4607/postgres-multi-mcp.git
cd postgres-multi-mcp

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check .
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client (Cursor)                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │ SSE
┌──────────────────────────────▼──────────────────────────────────┐
│                     postgres-multi-mcp Server                   │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ Config Loader  │  │ Connection Mgr  │  │   MCP Tools     │   │
│  │ (databases.yaml)│ │ (Pool per DB)   │  │ (list_schemas,  │   │
│  └───────┬────────┘  └────────┬────────┘  │  execute_sql,   │   │
│          │                    │           │  etc.)          │   │
│          └────────────────────┼───────────┘─────────────────┘   │
└───────────────────────────────┼─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
   ┌─────────┐            ┌─────────┐            ┌─────────┐
   │ Local   │            │  STAGED │            │  PROD   │
   │   DB    │            │   DB    │            │   DB    │
   └─────────┘            └─────────┘            └─────────┘
```

## Credits

This project is a fork of [postgres-mcp](https://github.com/crystaldba/postgres-mcp) by Crystal DBA. The original project provides excellent PostgreSQL analysis tools, and this fork extends it with multi-database support.

## License

MIT License - see [LICENSE](LICENSE) for details.
