#!/bin/bash
# Save as: ~/notify.sh
# Usage: ./notify.sh "Your message here"

MESSAGE=${1:-"Task completed"}
TOPIC="akash-dev-tasks"

curl -d "$MESSAGE" ntfy.sh/$TOPIC
