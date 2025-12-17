# Deploying Ashandy Agent to AWS EC2

This guide outlines the steps to deploy the application stack (FastAPI, PostgreSQL, Redis) to an AWS EC2 instance using Docker Compose.

![Architecture Diagram](deployment_architecture_1765967364341.png)

## Prerequisites
- An AWS Account
- A domain name (optional, but recommended for SSL)
- SSH Client (e.g., Terminal, PuTTY)

## Step 1: Launch EC2 Instance
1.  **Go to AWS Console > EC2 > Launch Instance**.
2.  **Name**: `Ashandy-Agent-Prod`.
3.  **OS Image**: Ubuntu Server 22.04 LTS (HVM).
4.  **Instance Type**: `t3.small` (recommended minimum, 2 vCPU, 2GB RAM) or `t2.medium`.
5.  **Key Pair**: Create a new key pair or utilize an existing one. Save the `.pem` file.
6.  **Network Settings**: Allow SSH traffic (Port 22), HTTPS (443), and Custom TCP (8000) from Anywhere (0.0.0.0/0). *Note: In a strict production environment, limit SSH to your IP.*

## Step 2: Configure Server
SSH into your instance:
```bash
ssh -i /path/to/your-key.pem ubuntu@your-ec2-public-ip
```

Install Docker and Docker Compose:
```bash
# Update packages
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up directory
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
sudo docker run hello-world
```

## Step 3: Deploy Application
1.  **Clone/Copy Code**:
    You can git clone your repository or use SCP to copy files.
    ```bash
    git clone <your-repo-url> app
    cd app
    ```

2.  **Environment Variables**:
    Create the `.env` file on the server. **Do not commit this to Git.**
    ```bash
    nano .env
    ```
    Paste the contents of your local `.env`. Ensure you update `DATABASE_URL` if using RDS, otherwise keep it matching `docker-compose.prod.yml` defaults.

3.  **Start Services**:
    Run the production compose file.
    ```bash
    sudo docker compose -f deployment/docker-compose.prod.yml up -d --build
    ```

4.  **Verify**:
    Check if containers are running:
    ```bash
    sudo docker compose -f deployment/docker-compose.prod.yml ps
    ```
    View logs:
    ```bash
    sudo docker compose -f deployment/docker-compose.prod.yml logs -f app
    ```

## Step 4: Accessing the App
Your API will be available at: `http://<your-ec2-public-ip>:8000`.
- API Docs: `http://<your-ec2-public-ip>:8000/docs`

> [!TIP]
> **Production Recommendation**: Set up Nginx as a reverse proxy on Port 80/443 to handle SSL (Let's Encrypt) and forward traffic to Port 8000. This avoids exposing Port 8000 directly.
