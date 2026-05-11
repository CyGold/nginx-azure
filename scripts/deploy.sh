#!/bin/bash

APP_VM_1="10.0.1.5"
APP_VM_2="10.0.1.6"
APP_USER="azureuser"
APP_DIR="/home/azureuser/weatherapp"
NGINX_CONFIG="/etc/nginx/sites-available/weatherapp"

deploy_to_server() {
    local SERVER=$1
    echo "--- Deploying to $SERVER ---"

    # Step 1: Remove server from Nginx rotation
    echo "Removing $SERVER from Nginx upstream..."
    sudo sed -i "s|server $SERVER:8000;|server $SERVER:8000 down;|" $NGINX_CONFIG
    sudo nginx -s reload
    sleep 2

    # Step 2: Deploy new code
    echo "Deploying new code to $SERVER..."
    ssh -o StrictHostKeyChecking=no $APP_USER@$SERVER \
        "cd $APP_DIR && source venv/bin/activate && pip install -q fastapi uvicorn && sudo systemctl restart weatherapp"
    sleep 3

    # Step 3: Health check
    echo "Running health check on $SERVER..."
    HEALTH=$(curl -s http://$SERVER:8000/health | grep -o '"healthy"')

    if [ "$HEALTH" == '"healthy"' ]; then
        echo "Health check passed — restoring $SERVER to rotation"
        sudo sed -i "s|server $SERVER:8000 down;|server $SERVER:8000;|" $NGINX_CONFIG
        sudo nginx -s reload
        echo "--- $SERVER deployment complete ---"
    else
        echo "ERROR: Health check failed for $SERVER — keeping it out of rotation"
        exit 1
    fi
}

echo "Starting zero-downtime deployment..."
deploy_to_server $APP_VM_1
sleep 2
deploy_to_server $APP_VM_2
echo "Deployment complete. Both servers back in rotation."