# three-tier-aplication
# CloudNotes — 3-Tier Practice App

A minimal three-tier app for practicing AWS deployments:

| Tier | Tech | What it does |
|---|---|---|
| Presentation (web) | HTML / CSS / JS | Login, register, notes UI |
| Application (app) | Python (Flask) | REST API, JWT auth, business logic |
| Data (DB) | MySQL | Stores users + notes |

```
three-tier-app/
├── frontend/        index.html, style.css, script.js
├── backend/         app.py, db.py, requirements.txt, .env.example
└── database/        schema.sql
```

---

## 1. Run it locally first

Get it working on your machine before touching AWS — it's much easier to debug.

### 1a. MySQL
```bash
mysql -u root -p < database/schema.sql
# creates database `appdb` with `users` and `notes` tables
```
Create an app-specific DB user (don't use root from the app):
```sql
CREATE USER 'appuser'@'%' IDENTIFIED BY 'changeme';
GRANT ALL PRIVILEGES ON appdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
```

### 1b. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit .env with your DB creds
python app.py                   # runs on http://localhost:5000
```
Check it's alive: `curl http://localhost:5000/api/health`

### 1c. Frontend
Just open `frontend/index.html` in a browser, or serve it:
```bash
cd frontend
python3 -m http.server 5500
```
Visit `http://localhost:5500`. Register a user, then log in.

If your browser blocks requests, check `CORS_ORIGINS` in `backend/.env` includes the frontend's origin.

---

## 2. Deploy the 3 tiers on AWS

This maps each tier onto separate AWS resources — the standard "3-tier VPC" reference architecture.

```
Internet
   │
   ▼
[ Tier 1: Web ]        S3 (static site) + CloudFront   — OR — EC2 in public subnet + ALB
   │  (HTTPS calls to API)
   ▼
[ Tier 2: App ]        EC2 (or ECS) in private subnet, behind an internal/external ALB
   │  (MySQL protocol, port 3306)
   ▼
[ Tier 3: Data ]       RDS for MySQL in private subnet (no public access)
```

### Step 0 — VPC setup
Create (or use the default) VPC with:
- 2 **public** subnets (for the ALB / bastion / NAT gateway), across 2 AZs
- 2 **private** subnets for the app tier (EC2 running Flask), across 2 AZs
- 2 **private** subnets for the data tier (RDS), across 2 AZs
- An Internet Gateway attached to the VPC, route table for public subnets pointing to it
- A NAT Gateway in a public subnet, route table for private subnets pointing to it (so app-tier EC2 can `pip install`, etc.)

### Step 1 — Data tier: RDS for MySQL
1. RDS console → Create database → MySQL → Free tier / dev-test template.
2. Place it in the **DB private subnets**, set "Public access" = **No**.
3. Create a security group `sg-db` that allows inbound **3306** only from `sg-app` (created below).
4. Set master username/password, note the **endpoint** once it's created.
5. Connect from a bastion or the app EC2 instance and run `database/schema.sql` against it.

### Step 2 — App tier: EC2 running Flask
1. Launch an EC2 instance (Amazon Linux 2023 or Ubuntu) in a **private app subnet**.
2. Security group `sg-app`: inbound 5000 (or 80 via a reverse proxy) only from the ALB's security group; outbound 3306 to `sg-db`.
3. Since it's in a private subnet, connect via **AWS Systems Manager Session Manager** (no need to open SSH/22 to the internet) or through a bastion host.
4. On the instance:
   ```bash
   sudo yum install -y python3 python3-pip git      # Amazon Linux
   git clone <your-repo-or-scp-the-backend-folder>
   cd backend
   pip3 install -r requirements.txt
   cp .env.example .env   # set DB_HOST to the RDS endpoint from Step 1
   pip3 install gunicorn
   gunicorn -w 3 -b 0.0.0.0:5000 app:app --daemon
   ```
5. (Optional but recommended) Put this behind an **internal Application Load Balancer** with target group health check on `/api/health`, and run gunicorn as a `systemd` service so it restarts on reboot.
6. For real deployments, put the app tier in an **Auto Scaling Group** across both private app subnets, with the ALB in front.

### Step 3 — Web tier: S3 + CloudFront (recommended for a static frontend)
1. Edit `frontend/script.js` → set `API_BASE` to your ALB's DNS name (or a custom domain), e.g. `https://api.yourdomain.com/api`.
2. Create an S3 bucket, enable **static website hosting**, upload `index.html`, `style.css`, `script.js`.
3. Put **CloudFront** in front of the bucket for HTTPS + caching + a custom domain (via ACM certificate + Route 53).
4. Alternative: run the frontend on an EC2 instance in the **public subnet** behind a public ALB instead of S3 — closer to a "classic" 3-tier diagram if that's what you want to practice.

### Step 4 — Wire security groups together
- `sg-web` (ALB/EC2 web tier): inbound 443/80 from `0.0.0.0/0`
- `sg-app` (EC2 app tier): inbound 5000 from `sg-web` only
- `sg-db` (RDS): inbound 3306 from `sg-app` only

This is the core of the exercise: each tier only talks to its immediate neighbor, nothing is open to the internet except the web tier.

### Step 5 — Test end to end
```bash
curl https://<your-cloudfront-or-alb-domain>/api/health
```
Then open the site URL in a browser, register, log in, and add a note — confirming traffic flows web → app → db and back.

---

## 3. Things worth practicing next
- Move `.env` secrets into **AWS Secrets Manager** or **SSM Parameter Store** instead of a plain file on EC2.
- Add **HTTPS** everywhere with ACM certificates.
- Put the app tier in an **Auto Scaling Group** with a launch template so it self-heals.
- Enable **RDS Multi-AZ** for the DB tier's high availability.
- Add **CloudWatch** alarms/logs for both tiers.
- Consider replacing raw EC2 with **ECS Fargate** for the app tier once you're comfortable with the basics.

## Notes on the app itself
- Passwords are hashed with bcrypt, never stored in plaintext.
- Auth uses stateless JWTs (`Authorization: Bearer <token>`), so the app tier can scale horizontally without sticky sessions.
- `/api/health` exists specifically for load balancer health checks.
