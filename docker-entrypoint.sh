#!/bin/bash

# Don't exit immediately so we can debug issues
# set -e

# Function to determine Docker host address
get_docker_host() {
    if ping -c 1 -w 1 host.docker.internal >/dev/null 2>&1; then
        echo "host.docker.internal"
    elif ping -c 1 -w 1 172.17.0.1 >/dev/null 2>&1; then
        echo "172.17.0.1"
    else
        echo ""
    fi
}

# Function to replace localhost in a string with the Docker host
replace_localhost() {
    local input_str="$1"
    local docker_host="$2"

    if [[ -z "$docker_host" ]]; then
        echo "WARNING: Cannot determine Docker host IP. Using original address." >&2
        echo "$input_str"
        return 1
    fi

    # Replace localhost with Docker host
    local new_str="${input_str/localhost/$docker_host}"
    if [[ "$new_str" != "$input_str" ]]; then
        echo "  Remapping: $input_str --> $new_str" >&2
    fi
    echo "$new_str"
    return 0
}

# Function to process databases.yaml file and replace localhost
process_databases_yaml() {
    local config_path="${DATABASES_CONFIG_PATH:-/app/databases.yaml}"
    local docker_host="$1"

    if [[ ! -f "$config_path" ]]; then
        echo "No databases.yaml found at $config_path" >&2
        return 0
    fi

    if [[ -z "$docker_host" ]]; then
        echo "No Docker host determined, skipping YAML processing" >&2
        return 0
    fi

    # Check if file contains localhost
    if grep -q "localhost" "$config_path"; then
        echo "Found localhost in databases.yaml, creating processed version..." >&2
        
        # Create a processed version of the config file
        local processed_path="/tmp/databases_processed.yaml"
        sed "s/localhost/$docker_host/g" "$config_path" > "$processed_path"
        
        # Update environment variable to point to processed file
        export DATABASES_CONFIG_PATH="$processed_path"
        echo "Using processed config at: $processed_path" >&2
    fi
}

# Determine Docker host address
docker_host=$(get_docker_host)
if [[ -n "$docker_host" ]]; then
    echo "Docker host detected: $docker_host" >&2
fi

# Process databases.yaml for localhost replacement
process_databases_yaml "$docker_host"

# Create a new array for the processed arguments
processed_args=()
processed_args+=("$1")
shift 1

# Process remaining command-line arguments for postgres:// or postgresql:// URLs that contain localhost
for arg in "$@"; do
    if [[ "$arg" == *"postgres"*"://"*"localhost"* ]]; then
        echo "Found localhost in database connection: $arg" >&2
        new_arg=$(replace_localhost "$arg" "$docker_host")
        processed_args+=("$new_arg")
    else
        processed_args+=("$arg")
    fi
done

# Check and replace localhost in DATABASE_URI if it exists (for backward compatibility)
if [[ -n "$DATABASE_URI" && "$DATABASE_URI" == *"postgres"*"://"*"localhost"* ]]; then
    echo "Found localhost in DATABASE_URI: $DATABASE_URI" >&2
    new_uri=$(replace_localhost "$DATABASE_URI" "$docker_host")
    export DATABASE_URI="$new_uri"
fi

# Check if SSE transport is specified and --sse-host is not already set
has_sse=false
has_sse_host=false

for arg in "${processed_args[@]}"; do
    if [[ "$arg" == "--transport" ]]; then
        # Check next argument for "sse"
        for next_arg in "${processed_args[@]}"; do
            if [[ "$next_arg" == "sse" ]]; then
                has_sse=true
                break
            fi
        done
    elif [[ "$arg" == "--transport=sse" ]]; then
        has_sse=true
    elif [[ "$arg" == "--sse-host"* ]]; then
        has_sse_host=true
    fi
done

# Add --sse-host if needed
if [[ "$has_sse" == true ]] && [[ "$has_sse_host" == false ]]; then
    echo "SSE transport detected, adding --sse-host=0.0.0.0" >&2
    processed_args+=("--sse-host=0.0.0.0")
fi

echo "----------------" >&2
echo "Executing command:" >&2
echo "${processed_args[@]}" >&2
echo "----------------" >&2

# Execute the command with the processed arguments
# Use exec to replace the shell with the Python process, making it PID 1
# This ensures signals (SIGTERM, SIGINT) are properly received
exec "${processed_args[@]}"
