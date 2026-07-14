# CloudNotes — 3-Tier Web Application on AWS

A full-stack 3-tier web application deployed on AWS with a production-style architecture: isolated network tiers, internal + external load balancing, and a private database layer with no public access.

**Live demo:** `http://<your-alb-dns-name>` *(update with your actual ALB DNS name)*

---

## Tech Stack

| Tier | Technology |
|---|---|
| Presentation | HTML, CSS, JavaScript (vanilla) |
| Application | Python (Flask), Gunicorn, JWT auth, bcrypt |
| Data | MySQL (Amazon RDS) |
| Infrastructure | AWS VPC, EC2, Application Load Balancer, Security Groups |

---

## Architecture

```
                        Internet
                            │
                            ▼
              ┌─────────────────────────┐
              │   Public ALB             │  internet-facing
              │   (sg-alb)               │  public subnets
              └───────────┬─────────────┘
                          │ HTTP 80
                          ▼
              ┌─────────────────────────┐
              │   Web Tier (EC2)         │  Apache/httpd
              │   (sg-web)               │  reverse proxy → /api/*
              │   public subnet          │
              └───────────┬─────────────┘
                          │ HTTP 80
                          ▼
              ┌─────────────────────────┐
              │   Internal ALB           │  private, internal-only
              │   (sg-internal-alb)      │  app-tier private subnets
              └───────────┬─────────────┘
                          │ 5000
                          ▼
              ┌─────────────────────────┐
              │   App Tier (EC2)         │  Flask + Gunicorn
              │   (sg-app)               │  JWT auth, bcrypt
              │   private subnet         │
              └───────────┬─────────────┘
                          │ 3306
                          ▼
              ┌─────────────────────────┐
              │   RDS (MySQL)            │  no public access
              │   (sg-db)                │  private DB subnets
              └─────────────────────────┘
```

### Network isolation

Each security group only accepts traffic from the tier immediately in front of it:

| Security Group | Allows inbound from | Port |
|---|---|---|
| `sg-alb` | Internet (`0.0.0.0/0`) | 80/443 |
| `sg-web` | `sg-alb` only | 80 |
| `sg-internal-alb` | `sg-web` only | 80 |
| `sg-app` | `sg-internal-alb` only | 5000 |
| `sg-db` | `sg-app` only | 3306 |

No tier is reachable except from its direct neighbor — the app and database tiers have no route from the public internet at all.

---

## Features

- User registration and login with hashed passwords (bcrypt)
- Stateless authentication via JWT — no server-side session storage, so the app tier can scale horizontally
- A simple notes CRUD feature to demonstrate authenticated API calls end to end
- Health check endpoint (`/api/health`) for load balancer target group checks

---

## Project structure

```
├── index.html          # Login / register / dashboard UI
├── style.css            # Styling
├── script.js            # Frontend logic, calls the API at /api
├── app.py               # Flask routes: register, login, notes, health
├── db.py                # MySQL connection pooling
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── schema.sql            # Database schema (users, notes tables)
```

---

## Running locally

```bash
# 1. Database
mysql -u root -p < schema.sql

# 2. Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in your DB credentials and a JWT secret
python app.py             # runs on http://localhost:5000

# 3. Frontend
# open index.html in a browser, or serve it:
python3 -m http.server 5500
```

---

## AWS Deployment Summary

1. **VPC** — 2 public subnets, 4 private subnets (2 for app tier, 2 for DB tier), across 2 Availability Zones, with a NAT Gateway for outbound access from private subnets
2. **RDS (MySQL)** — deployed in the private DB subnets, no public accessibility, reachable only from the app tier
3. **App tier (EC2)** — Flask app run via Gunicorn, managed as a systemd service, in a private subnet behind an internal ALB
4. **Web tier (EC2)** — Apache serving the static frontend and reverse-proxying `/api/*` requests to the internal ALB
5. **Load balancing** — a public-facing ALB in front of the web tier, and an internal ALB in front of the app tier, so neither tier's specific EC2 instance needs to be known by the layer in front of it

---

## What this project demonstrates

- Designing and implementing tiered network isolation using AWS security groups
- Deploying a stateless authentication system suitable for horizontal scaling
- Configuring reverse proxies (Apache) to bridge a public web tier to a private application tier
- Debugging real infrastructure issues: SELinux file context restrictions, security group misconfigurations, reverse proxy setup, RDS connectivity
- Using AWS Systems Manager Session Manager for secure, keyless access to instances in private subnets

## Roadmap

- [ ] Wrap both tiers in Auto Scaling Groups for self-healing and horizontal scaling
- [ ] Move secrets (`JWT_SECRET`, DB credentials) into AWS Secrets Manager
- [ ] Add HTTPS via ACM certificate on the public ALB
- [ ] Add CloudWatch monitoring and alarms
- [ ] Automate deployment with a CI/CD pipeline
