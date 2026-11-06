# Build guide: Northside Gym member portal

This is the only file you need open while building. Work from top to bottom, because each step needs the one before it. Everything is built from an empty account in `eu-west-2` (London).

After every step:

1. Tick the box.
2. Take the 📸 screenshot and save it to `_working/raw-screenshots/`.
3. Add two lines to `_working/build-log.md`: what you did, and any error with its fix.

**Mock data only.** The site is HTTP, so passwords cross the internet unencrypted. Register only made-up accounts.

| Part | Steps | Roughly |
| --- | --- | --- |
| 0. Before you start | 0 | 10 minutes |
| A. Network, servers and load balancer | 1 to 3 | 1.5 hours |
| B. Phase 1: RDS | 4 to 6 | 1.5 hours |
| C. Phase 2: DynamoDB | 7 to 9 | 45 minutes |
| D. Teardown | 10 | 30 minutes |

The NAT Gateway, load balancer and public IPv4 addresses cost about $0.13 an hour while they run. Do it all in one sitting, or tear down at the end of each session and rebuild from step 1.

## Names used throughout

| Item | Name | Value |
| --- | --- | --- |
| VPC | `gym-vpc` | `10.20.0.0/16` |
| Public subnets (ALB, NAT) | `gym-public-a`, `gym-public-b` | `10.20.1.0/24` (2a), `10.20.2.0/24` (2b) |
| App subnets (web servers) | `gym-app-a`, `gym-app-b` | `10.20.11.0/24` (2a), `10.20.12.0/24` (2b) |
| DB subnets (RDS) | `gym-db-a`, `gym-db-b` | `10.20.21.0/24` (2a), `10.20.22.0/24` (2b) |
| Security groups | `gym-alb-sg`, `gym-web-sg`, `gym-db-sg` | see step 1.6 |
| Web server role | `gym-web-role` | Session Manager, later DynamoDB |
| Database | `gym-db` | RDS for PostgreSQL, database `gym` |
| Table | `gym-checkins` | DynamoDB |

---

## 0. Before you start

- [x] **0.1 Budget alert.** Billing → Budgets: make sure a monthly cost budget with an email alert exists.
- [x] **0.2 Region.** Choose **Europe (London) eu-west-2** at the top right and stay in it.
- [x] **0.3 Repo.** The project is pushed to GitHub as a **public** repo, so the servers can clone it in step 5. Push again whenever you change the code; to update a running server, run `cd /opt/aws-gym-member-portal && sudo git pull && sudo bash scripts/install-app.sh`.

📸 Screenshot:
```text
00-budget
```

---

## Part A. Network, servers and load balancer

### Step 1. Network

- [x] **1.1 VPC.** VPC → Your VPCs → Create VPC → **VPC only**. Name `gym-vpc`, CIDR `10.20.0.0/16`.
- [x] **1.2 Subnets.** Subnets → Create subnet in `gym-vpc`, using the six names and CIDRs in the table above, three in eu-west-2a and three in eu-west-2b.
- [x] **1.3 Internet gateway.** Create `gym-igw` and attach it to `gym-vpc`.
- [x] **1.4 NAT Gateway.** NAT gateways → Create: name `gym-nat`, subnet `gym-public-a`, connectivity **Public**, then **Allocate Elastic IP**. One NAT keeps the cost down; it lets the web servers download packages without being reachable from the internet.
- [x] **1.5 Route tables.** Create three, then associate the subnets:

  | Route table | Extra route | Associated subnets |
  | --- | --- | --- |
  | `gym-public-rt` | `0.0.0.0/0` → `gym-igw` | `gym-public-a`, `gym-public-b` |
  | `gym-app-rt` | `0.0.0.0/0` → `gym-nat` | `gym-app-a`, `gym-app-b` |
  | `gym-db-rt` | none (local only) | `gym-db-a`, `gym-db-b` |

- [x] **1.6 Security groups.** Each one allows only the layer in front of it:

  | Security group | Inbound rule | Why |
  | --- | --- | --- |
  | `gym-alb-sg` | HTTP 80 from `0.0.0.0/0` | Visitors reach the load balancer |
  | `gym-web-sg` | HTTP 80 from `gym-alb-sg` | Only the ALB reaches the web servers |
  | `gym-db-sg` | PostgreSQL 5432 from `gym-web-sg` | Only the web servers reach the database |

  Network ACLs stay at the default (allow all). In this project the security groups do the filtering. NACL hardening is covered in a separate project.

📸 Screenshot:
```text
01-subnets
```

📸 Screenshot:
```text
02-route-tables
```

📸 Screenshot:
```text
03-security-groups
```

### Step 2. Web servers

- [x] **2.1 IAM role.** IAM → Roles → Create role: trusted entity **AWS service → EC2**, policy **AmazonSSMManagedInstanceCore**, name `gym-web-role`. This lets you open a shell with Session Manager, so there's no SSH key, no bastion and no port 22.
- [x] **2.2 Launch two instances.** EC2 → Launch instances, twice:

  | Setting | Value |
  | --- | --- |
  | Name | `gym-web-a`, then `gym-web-b` |
  | AMI | Amazon Linux 2023 |
  | Type | `t3.micro` |
  | Key pair | **Proceed without a key pair** |
  | Subnet | `gym-app-a`, then `gym-app-b` |
  | Auto-assign public IP | **Disable** |
  | Security group | `gym-web-sg` |
  | IAM instance profile (Advanced details) | `gym-web-role` |
  | User data (Advanced details, at the bottom) | Paste `scripts/user-data.sh` |

  The user data installs the prerequisites: Apache (httpd), Python, Git and the PostgreSQL client.

- [x] **2.3 Connect.** After about 2 minutes: select `gym-web-a` → **Connect → Session Manager → Connect**. You get a shell in the browser. If Connect is greyed out, wait a few more minutes and check the role is attached.

📸 Screenshot (both running, no public IP):
```text
04-instances
```

📸 Screenshot:
```text
05-session-manager
```

### Step 3. Load balancer

- [x] **3.1 Target group.** EC2 → Target groups → Create:
  - type Instances, name `gym-tg`, HTTP 80, VPC `gym-vpc`
  - health check path `/health`
  - register `gym-web-a` and `gym-web-b`
- [x] **3.2 Load balancer.** EC2 → Load balancers → Create **Application Load Balancer**:
  - name `gym-alb`, internet-facing
  - VPC `gym-vpc`, subnets `gym-public-a` and `gym-public-b`
  - security group `gym-alb-sg` (remove default)
  - listener HTTP 80 → `gym-tg`
- [x] **3.3** Copy the ALB's DNS name into your build log. The targets show **unhealthy** until the app is installed in step 5. That's expected.

📸 Screenshot:
```text
06-alb
```

---

## Part B. Phase 1: RDS for registration, login and the profile page

### Step 4. Database

- [x] **4.1 DB subnet group.** RDS → Subnet groups → Create DB subnet group:
  - name `gym-db-subnets`, VPC `gym-vpc`
  - Availability Zones `eu-west-2a` and `eu-west-2b`
  - subnets `gym-db-a` (`10.20.21.0/24`) and `gym-db-b` (`10.20.22.0/24`) only

  You don't create subnets here: `gym-db-a` and `gym-db-b` already exist from step 1.2.

  *Why:* A subnet group is the list of subnets RDS is allowed to place the database in. AWS insists on at least two Availability Zones, so it can move the database to the other zone (for Multi-AZ, or during recovery) without you changing any settings. Only the database subnets go in, which keeps the database in its own tier with no route to the internet.

- [x] **4.2 Create the database.** RDS → Create database → Standard create:
  - PostgreSQL, **Free tier** template, `db.t4g.micro`, 20 GiB
  - identifier `gym-db`, master username `dbadmin`, self-managed password (keep it in your password manager)
  - VPC `gym-vpc`, subnet group `gym-db-subnets`, public access **No**, security group `gym-db-sg` (remove default)
  - Additional configuration: initial database name `gym`, backup retention 1 day, encryption on

  *Why each setting:*
  - **Free tier template:** locks the form to free-tier choices (Single-AZ, micro instance), so you can't pick a paid option by accident.
  - **Identifier vs database name:** `gym-db` is the RDS instance (the server). `gym` is a database inside it; one instance can hold many databases.
  - **Master user `dbadmin`:** the database's admin account, like root. You use it only for setup. The app gets its own limited user in step 5.
  - **Public access No:** the database gets no public IP address, so nothing on the internet can reach it, whatever the security group says.
  - **`gym-db-sg`:** the database's firewall. Its one rule allows port 5432 only from instances in `gym-web-sg`.
  - **Encryption:** encrypts the storage and backups at rest with an AWS-managed key, at no extra cost.
  - **Backups 1 day:** keeps automated backups so you can restore to any point in the last day. One day keeps storage small.

- [x] **4.3** Wait for **Available** (about 10 minutes), then copy the endpoint into your build log.

  *Why:* The endpoint is a DNS name, such as `gym-db.xxxx.eu-west-2.rds.amazonaws.com`, not an IP address. RDS can change the IP behind it (after a restart or failover), and the name always points to the right place. That's why the app connects by name.

📸 Screenshot (Connectivity tab; redact the account-specific part of the endpoint):
```text
07-rds-available
```

### Step 5. Schema and app on `gym-web-a`

Open a Session Manager shell on `gym-web-a`, then:

- [x] **5.1 Get the code:**

  ```bash
  sudo git clone https://github.com/<your-username>/aws-gym-member-portal.git /opt/aws-gym-member-portal
  cd /opt/aws-gym-member-portal
  ```

  If `git` isn't found, the user data hasn't finished yet. Wait a minute and try again.

  *Why:* Both servers pull the same code from GitHub, so they always run the same version. `/opt` is the usual Linux folder for add-on software. It belongs to root, hence `sudo`.

- [x] **5.2 Install the app.** This copies the app to `/opt/gym-app`, sets up Python and the service, and points Apache at it:

  ```bash
  sudo bash scripts/install-app.sh
  ```

  *Why each part:*
  - **Virtual environment (`venv`):** the app's Python packages go in their own folder, so they never clash with the system's Python.
  - **gunicorn:** a production web server for Python apps. Flask's built-in server is only for development.
  - **systemd service:** starts the app at boot and restarts it if it crashes, like any other Linux service.
  - **Apache as a reverse proxy:** Apache keeps listening on port 80 and passes requests to gunicorn on `127.0.0.1:8000`. gunicorn is never exposed to the network, and the ALB and security groups stay on port 80.

- [x] **5.3 Load the schema** as the master user:

  ```bash
  psql "host=<rds-endpoint> dbname=gym user=dbadmin sslmode=require" -f app/schema.sql
  ```

  *Why:* The schema creates the tables and their rules: each email must be unique, and every member must point at a real plan (a foreign key). It also adds three sample plans and the `gym_app` user. It needs the admin account because creating tables and users is an admin job. It runs once because both servers share one database, and `IF NOT EXISTS` makes it safe to run again. `sslmode=require` encrypts the connection between the server and RDS.

- [x] **5.4 Set the app user's password**, without it ever touching a file:

  ```bash
  psql "host=<rds-endpoint> dbname=gym user=dbadmin sslmode=require"
  ```

  Log in with the `dbadmin` password from the console. At the `gym=>` prompt, type `\password gym_app`, enter a **new, different** password twice (save it in your password manager), then `\q`.

  This is a second password. The console password belongs to `dbadmin`; `gym_app` was only just created by the schema, with no password.

  *Why:* `gym_app` is the **least-privilege** account the app logs in with. It can read plans and read or add members, nothing more. Setting the password with `\password` keeps it out of `schema.sql`, Git and your shell history.

- [x] **5.5 Settings.** Generate a secret key and copy it into your build log; you'll reuse it on `gym-web-b`:

  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  sudo nano /etc/gym-app.env
  ```

  Fill in `DB_HOST`, `DB_PASSWORD` (the `gym_app` password) and `SECRET_KEY`. Leave `CHECKINS_TABLE` empty.

  *Why:*
  - **Settings outside the code:** the same code runs anywhere, and secrets never go into Git. The file is `chmod 600`, so only root can read it.
  - **`SECRET_KEY`:** after login, Flask stores who you are in a cookie in your browser, signed with this key so nobody can forge it. Both servers need the same key so a cookie made by one is trusted by the other.
  - **Empty `CHECKINS_TABLE`:** switches the DynamoDB feature off until part C.

- [x] **5.6 Start it:**

  ```bash
  sudo systemctl restart gym-app
  curl -s localhost/health
  ```

  This should print `ok`.

  *Why:* `/health` is the page the load balancer checks. It deliberately doesn't touch the database. If it did, a database problem would mark **both** servers unhealthy, and the ALB would have nowhere to send anyone.

📸 Screenshot:
```text
08-schema-and-health
```

**If something fails:**

- `curl` returns 503: the app isn't running. Run `sudo journalctl -u gym-app -n 30` and read the last error.
- The log shows a database timeout: check `gym-db-sg` allows 5432 from `gym-web-sg`.
- A login error mentioning `gym_app`: redo 5.4 and check `DB_PASSWORD`.

### Step 6. Second server and phase 1 tests

- [ ] **6.1 `gym-web-b`.** Open a Session Manager shell on `gym-web-b` and repeat 5.1, 5.2, 5.5 and 5.6. Skip the schema (5.3 and 5.4), because the database is shared. Use the **same** `SECRET_KEY`, so a login made on one server works on the other.

  *Why:* Two servers in two Availability Zones means the site survives one server, or one whole zone, failing. The servers keep nothing of their own: members live in RDS and logins live in signed cookies. That makes them **stateless**, so any server can answer any request.

- [ ] **6.2** Target groups → `gym-tg` → Targets: both **healthy**.

  *Why:* The ALB only sends visitors to targets that pass the `/health` check. Two healthy targets means traffic is being shared.

📸 Screenshot:
```text
09-targets-healthy
```

Open the ALB DNS name in your browser, then run the tests and record each result in `docs/test-results.md`:

- [ ] **T1 Register.** Create a made-up member. You land on a profile page with their name, plan, price and renewal date.

  📸 Screenshot:
  ```text
  10-profile
  ```

  *Proves:* the full path works: browser → ALB → web server → RDS. Registering writes a row, and the profile reads it back by joining `members` to `plans`.

- [ ] **T2 Data loads from RDS.** On a web server, run:

  ```bash
  psql "host=<rds-endpoint> dbname=gym user=dbadmin sslmode=require" -c "INSERT INTO plans (name, monthly_price, perks) VALUES ('Student', 14.99, 'Off-peak, student ID');"
  ```

  Reload `/register`. Student appears in the dropdown with no code change.

  📸 Screenshot:
  ```text
  11-dynamic-plans
  ```

  *Proves:* the page is **dynamic**: what it shows comes from the database at the moment it's loaded, not from HTML written in advance.

- [ ] **T3 Login refused.** Log in with a wrong password. You see "Email or password is incorrect", the same message as for an unknown email.

  📸 Screenshot:
  ```text
  12-login-refused
  ```

  *Proves:* the site doesn't reveal which emails are registered. Different messages would let an attacker test emails one by one (called user enumeration).

- [ ] **T4 Passwords hashed.** As `dbadmin`: `SELECT email, password_hash FROM members;`. You see hashes starting `scrypt:`, never the password.

  📸 Screenshot:
  ```text
  13-hashed-passwords
  ```

  *Proves:* passwords are stored as one-way hashes. At login, the app hashes what you type and compares the two. scrypt is slow on purpose, so guessing passwords from a stolen database takes far longer.

- [ ] **T5 Database least privilege.** As `gym_app`: `DELETE FROM members;`. You get "permission denied for table members".

  📸 Screenshot:
  ```text
  14-least-privilege-db
  ```

  *Proves:* even if someone took over the app, its database account couldn't delete members or change plans.

- [ ] **T6 RDS not public.** RDS → `gym-db` → Connectivity & security shows **Publicly accessible: No**, and `gym-db-sg` has one inbound rule, from `gym-web-sg`.

  📸 Screenshot:
  ```text
  15-rds-not-public
  ```

  *Proves:* **defence in depth**, two separate locks. No public IP means the internet can't reach the database at all. Inside the VPC, the security group rule names another security group rather than an IP range, so only instances in `gym-web-sg` get in.

- [ ] **T7 Load balancing.** Refresh the profile several times. The footer server name changes and you stay logged in.

  📸 Screenshot:
  ```text
  16-load-balanced.gif
  ```

  *Proves:* the ALB spreads requests across both servers, and the shared `SECRET_KEY` keeps you logged in whichever one answers.

- [ ] **T8 One server down.** Run `sudo systemctl stop gym-app` on `gym-web-a`. Its target goes unhealthy and the site keeps working. Then run `sudo systemctl start gym-app`.

  📸 Screenshot:
  ```text
  17-one-server-down
  ```

  *Proves:* **high availability**. The health check notices the failure within about a minute, and the ALB stops sending traffic to that server.

---

## Part C. Phase 2: DynamoDB check-ins

### Step 7. Table and private route

- [ ] **7.1 Table.** CloudShell (`eu-west-2`):

  ```bash
  aws dynamodb create-table --table-name gym-checkins --region eu-west-2 \
    --attribute-definitions AttributeName=member_id,AttributeType=S AttributeName=checked_in_at,AttributeType=S \
    --key-schema AttributeName=member_id,KeyType=HASH AttributeName=checked_in_at,KeyType=RANGE \
    --billing-mode PROVISIONED --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
  ```

  *Why:* In DynamoDB you design the keys around the question the app asks, here "this member's latest visits".
  - **Partition key `member_id`:** decides where an item is stored. All of one member's visits sit together, so one query fetches them.
  - **Sort key `checked_in_at`:** orders items within a member. ISO times like `2026-11-05T18:02:11` sort correctly as text, so "newest first" is just reading backwards.
  - **No other columns defined:** DynamoDB has no fixed schema. You only declare the key attributes; each item can carry anything else, like `server`.
  - **Provisioned 5 RCU and 5 WCU:** a fixed amount of read and write capacity. The always-free allowance covers 25 of each, but only in provisioned mode.

- [ ] **7.2 Gateway endpoint.** VPC → Endpoints → Create:
  - service `com.amazonaws.eu-west-2.dynamodb`, type **Gateway**
  - VPC `gym-vpc`, route table `gym-app-rt`

  *Why:* DynamoDB is a public AWS service. Without an endpoint, the private servers would reach it through the NAT Gateway, which charges for every GB. A gateway endpoint adds a route that sends DynamoDB traffic straight to it over AWS's own network: free, and never touching the internet. Gateway endpoints only exist for DynamoDB and S3; other services use interface endpoints, which cost money.

- [ ] **7.3** `gym-app-rt` now has a `pl-` route to the endpoint.

  *Why:* `pl-` is a **prefix list**: AWS's maintained list of DynamoDB's IP ranges in this region. Any traffic to those ranges now takes the endpoint route instead of the NAT.

📸 Screenshot:
```text
18-dynamodb-table
```

📸 Screenshot:
```text
19-endpoint-route
```

### Step 8. Permission

- [ ] **8.1** IAM → Roles → `gym-web-role` → Add permissions → Create inline policy → JSON. Paste `app/deploy/dynamodb-policy.json` with your account ID filled in, and name it `gym-checkins-access`.

  *Why:* RDS uses a username and password, but DynamoDB uses IAM. The instance role hands each server short-lived credentials automatically, and the app's AWS library (boto3) finds them by itself, so there are **no access keys** stored on the server. The policy allows two actions (`PutItem` to record a visit, `Query` to list visits) on one table only. It's an inline policy because it belongs to this role alone.

📸 Screenshot:
```text
20-iam-policy
```

### Step 9. Switch on and test

- [ ] **9.1** On **both** servers, set `CHECKINS_TABLE=gym-checkins` in `/etc/gym-app.env`, then run `sudo systemctl restart gym-app`.

  *Why:* the same code ran in phase 1 with this feature switched off. Changing one setting switches it on, without a new deployment; this is called a feature flag. The restart makes the app re-read its settings file.

- [ ] **T9 Check in.** Press **Check in now** three times. Three visits appear, newest first, and DynamoDB → Explore items shows the same items.

  📸 Screenshot:
  ```text
  21-checkins
  ```

  *Proves:* the write (`PutItem`) and read (`Query` on `member_id`, newest first, limit 5) both work through the endpoint and the role.

- [ ] **T10 Both servers write.** After a few check-ins and refreshes, "Recorded by" shows both server names.

  📸 Screenshot:
  ```text
  22-both-servers
  ```

  *Proves:* both servers share one table, so visits recorded on either server show up on both.

- [ ] **T11 IAM least privilege.** On a web server:

  ```bash
  aws dynamodb scan --table-name gym-checkins --region eu-west-2
  ```

  You get AccessDenied, because the role allows only `PutItem` and `Query`.

  📸 Screenshot:
  ```text
  23-least-privilege-iam
  ```

  *Proves:* the role can do only what the app needs. A `Scan` reads the whole table, every member's visits, so the app is never allowed to run one.

---

## Part D. Teardown (in this order)

*Why this order:* AWS won't delete a resource while something still depends on it. The database holds onto its subnet group, and the VPC can't go while anything still has a network interface in it (the ALB, NAT Gateway, instances or RDS). Delete from the top down.

- [ ] **10.1** DynamoDB: delete `gym-checkins`. VPC: delete the DynamoDB endpoint.
- [ ] **10.2** RDS: delete `gym-db`. Untick the final snapshot, tick "delete automated backups", and wait until it's gone. Then delete `gym-db-subnets`.

  *Why:* a final snapshot or kept backups would carry on costing storage after the database is gone.

- [ ] **10.3** EC2: delete `gym-alb`, then `gym-tg`, then terminate `gym-web-a` and `gym-web-b`.
- [ ] **10.4** VPC: delete `gym-nat` and wait for **Deleted**. Then release its Elastic IP.

  *Why:* the NAT Gateway charges every hour it exists, and an Elastic IP is charged even when it isn't attached to anything. These two are the classic forgotten bills.

- [ ] **10.5** VPC: delete `gym-vpc`. This removes the subnets, route tables, internet gateway and security groups with it.
- [ ] **10.6** IAM: delete `gym-web-role`.
- [ ] **10.7** Next day: Billing → Bills shows nothing still charging.

  *Why:* billing data lags by several hours, so the next day is the first reliable check.

📸 Screenshot:
```text
24-teardown-complete
```

Log the time in the build log, because billing stops here.

---

## After the build

1. Redact the account ID, endpoints and your IP in the raw screenshots, then copy them to `screenshots/` with the names above.
2. Fill in `docs/test-results.md` and `docs/lessons-learned.md` from your build log.
3. Open `diagrams/architecture.drawio` in draw.io and tidy it to match what you built. Then **File → Export as → PNG**, zoom 200%, saved as `diagrams/architecture.png`. The README already links it.
4. Fill in the README's placeholders, then commit and push.