# Deploying to AWS: EC2 + RDS MySQL

This guide moves the Student Record Management System to AWS:

- **EC2** (Ubuntu 24.04) runs Nginx, Gunicorn and the Flask app.
- **RDS for MySQL 8** stores the data. It is private: only the EC2 instance can reach it.

```
Browser ──:80──► Nginx ──► Gunicorn :8000 ──► Flask ──:3306──► RDS MySQL (private)
                 └──────────── EC2 instance ────────────┘
```

**Where each command runs.** Every block is labelled:

| Label | Where |
|---|---|
| 🖥️ **Windows** | Your own computer (Command Prompt or PowerShell) |
| ☁️ **EC2** | The SSH or browser-based terminal connected to your EC2 instance |
| 🗄️ **RDS** | The `mysql>` prompt opened **from EC2** and connected to the RDS endpoint |
| 🌐 **Console** | Clicks in the AWS web console |

Use one AWS Region for everything (for example **Asia Pacific (Mumbai) ap-south-1**). Check the Region name at the top right of the console before every step; resources in another Region will not appear.

---

## 0. Before you start

- Push the project to a GitHub repository (see the README). Make sure `.env` is **not** in it.
- Never share AWS access keys, your `.pem` key file or database passwords with anyone. This guide does not need access keys at all.
- Keep a note of every resource you create; you will delete them in step 17.

## 1. Check AWS credits and eligibility 🌐

1. Sign in to https://console.aws.amazon.com/ . If you need an account, sign up at https://aws.amazon.com/free/ (it needs an email address, a phone number and a payment card for verification).
2. Open **Billing and Cost Management → Credits** to see credits and their expiry dates. Open **Billing → Free Tier** to see what your account includes.
3. Understand your plan. Free-tier rules and credits **differ by account type, sign-up date and Region**, and AWS has changed them over time. Some plans cover only certain services or instance types, and credits expire. Read the Credits and Free Tier pages for *your* account instead of assuming.
4. Set a safety net: **Billing → Budgets → Create budget → Zero spend budget** (or a small monthly budget such as 5 USD) with your email, so you are warned if charges appear.
5. Things that can cost money even for a tiny project: EC2 instance hours, EBS disks, the **public IPv4 address** (charged per hour), RDS instance hours, RDS storage and backups, and data transfer.

## 2. Create the EC2 instance 🌐

### 2a. Create a key pair

1. **EC2 → Network & Security → Key Pairs → Create key pair**.
2. Name: `student-app-key`, type **RSA**, format **.pem** (OpenSSH/PowerShell/Command Prompt) → **Create**. The file downloads once. Keep it safe, never commit it.

### 2b. Create the web security group

**EC2 → Security Groups → Create security group**

- Name: `ec2-web-sg`, description: `Web access for student app`, VPC: default.
- Inbound rules:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** | Only your current IP can log in. Never use `0.0.0.0/0` for SSH |
| HTTP | 80 | Anywhere-IPv4 (`0.0.0.0/0`), or **My IP** if only you will test | The website |

- Outbound: leave the default (all traffic), which lets the server install packages and reach RDS.

"My IP" changes when you change networks (home, college, mobile hotspot). If SSH stops working later, edit the rule and choose **My IP** again.

### 2c. Launch the instance

**EC2 → Instances → Launch instances**

- Name: `student-app-server`
- AMI: **Ubuntu Server 24.04 LTS** (marked free tier eligible if your account has it)
- Instance type: pick a small type that the console marks **Free tier eligible** (commonly `t3.micro` or `t2.micro`, depending on Region and account). If none is marked, choose `t3.micro` and confirm the price in the console.
- Key pair: `student-app-key`
- Network settings → **Edit**: default VPC, a public subnet, **Auto-assign public IP: Enable**, **Select existing security group → `ec2-web-sg`**
- Storage: **8 GiB gp3** (default) is enough
- Click **Launch instance**, then open it and wait for *Instance state: Running* and *Status checks: 2/2 passed*.
- Copy the **Public IPv4 address**. It changes if you stop and start the instance; that is fine for this demo (no Elastic IP needed).

## 3. Create the RDS MySQL database 🌐

### 3a. Create the database security group

**EC2 → Security Groups → Create security group**

- Name: `rds-mysql-sg`, description: `MySQL from EC2 only`, VPC: default.
- Inbound rule:

| Type | Port | Source |
|---|---|---|
| MySQL/Aurora | 3306 | **Custom → select the `ec2-web-sg` security group** (type `sg-` and pick it from the list) |

Using the EC2 security group as the source (instead of an IP address) means *only* instances in that group can connect, even if the EC2 IP changes. Never allow `0.0.0.0/0` on port 3306.

### 3b. Create the RDS instance

**RDS → Databases → Create database**

- Creation method: **Standard create**
- Engine: **MySQL**, version **8.0.x** (the latest 8.0 minor version offered)
- Templates: **Free tier** if shown for your account, otherwise **Dev/Test** (never Production)
- Availability: **Single-AZ / Single DB instance** (no Multi-AZ standby)
- DB instance identifier: `student-db`
- Master username: `admin`
- Credentials management: **Self managed**, then enter a strong master password. Use letters and digits only (RDS forbids `/`, `"`, `@` and spaces). Store it in a password manager.
- Instance class: the smallest burstable class offered, for example `db.t4g.micro` or `db.t3.micro` (the Free tier template selects an eligible one)
- Storage: **gp3, 20 GiB**, and **untick Enable storage autoscaling**
- Connectivity:
  - Compute resource: **Don't connect to an EC2 compute resource** (we set the security group ourselves)
  - VPC: default; DB subnet group: default
  - **Public access: No**
  - VPC security group: **Choose existing → `rds-mysql-sg`** and remove `default`
- Database authentication: **Password authentication**
- Additional configuration:
  - Initial database name: leave empty (`database.sql` creates it)
  - Backup retention: **1 day** (backups use storage and can cost money; use 0 only if you accept having no restore option)
  - Untick **Enhanced monitoring** and **Performance Insights**
  - Untick **Enable deletion protection** (so you can delete it in step 17)
- Click **Create database**. It takes 5-15 minutes. When *Status: Available*, open it and copy the **Endpoint** (looks like `student-db.xxxxxxxx.ap-south-1.rds.amazonaws.com`).

## 4. Connect to EC2

### Option A: SSH from Windows 🖥️

Open Command Prompt in the folder that holds the `.pem` file (for example `cd %USERPROFILE%\Downloads`). Windows 10/11 includes the OpenSSH client.

```
ssh -i student-app-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Type `yes` to trust the host. If you get an "unprotected private key file" error, restrict the file permissions:

```
icacls student-app-key.pem /inheritance:r
icacls student-app-key.pem /grant:r "%USERNAME%:R"
```

### Option B: Browser-based terminal 🌐

**EC2 → Instances → select the instance → Connect → EC2 Instance Connect → Connect**. No key file is needed. This also requires SSH (port 22) to be reachable from AWS's connect service, so if it fails, SSH from your own computer (Option A) is the simpler route with the "My IP" rule.

The prompt should look like `ubuntu@ip-172-31-x-x:~$`. Everything in steps 5-14 runs here.

## 5. Install system packages ☁️ EC2

```
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx mysql-client
python3 --version
```

`mysql-client` provides the `mysql` command we use to talk to RDS.

## 6. Clone the project ☁️ EC2

```
cd ~
git clone https://github.com/YOUR_USERNAME/StudentRecordManagement.git
cd StudentRecordManagement
ls -a
```

A public repository clones without a login. For a private repository, GitHub asks for a username and a **personal access token** (GitHub → Settings → Developer settings → Fine-grained tokens, read-only access to this one repository). Do not paste the token into any file.

## 7. Test the connection to RDS ☁️ EC2

```
mysql -h YOUR_RDS_ENDPOINT -u admin -p
```

Enter the master password. A `mysql>` prompt means the security groups are correct. If it hangs, go to the troubleshooting table (step 16).

## 8. Create the table and application user in RDS 🗄️ RDS

First leave the prompt (`EXIT;`), then load the schema from the project folder. This runs `database.sql` against RDS:

```
cd ~/StudentRecordManagement
mysql -h YOUR_RDS_ENDPOINT -u admin -p < database.sql
```

Then open the RDS prompt again and create the least-privilege app user:

```
mysql -h YOUR_RDS_ENDPOINT -u admin -p
```

```sql
CREATE USER 'student_app'@'%' IDENTIFIED BY 'YourStrongAppPassword1';
GRANT SELECT, INSERT, UPDATE, DELETE ON student_management.* TO 'student_app'@'%';
FLUSH PRIVILEGES;
SHOW TABLES FROM student_management;
SELECT COUNT(*) FROM student_management.students;
EXIT;
```

`'%'` is acceptable here because the security group already limits who can connect. Use a different password from the master password (letters and digits only keeps `.env` simple).

Optional: if you do not want the sample students in your demo, run `DELETE FROM student_management.students;` as `admin` and add your own through the website.

## 9. Install Python dependencies ☁️ EC2

```
cd ~/StudentRecordManagement
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 10. Configure environment variables with the RDS endpoint ☁️ EC2

```
cp .env.example .env
nano .env
```

Set the values (no quotes needed):

```
DB_HOST=student-db.xxxxxxxx.ap-south-1.rds.amazonaws.com
DB_PORT=3306
DB_USER=student_app
DB_PASSWORD=YourStrongAppPassword1
DB_NAME=student_management
SECRET_KEY=paste_a_long_random_value_here
```

Generate the secret with `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste it. Save in nano with `Ctrl+O`, `Enter`, `Ctrl+X`. Then protect the file:

```
chmod 600 .env
```

This is the only change needed to move from local MySQL to RDS. The code stays the same.

## 11. Run with Gunicorn (quick test) ☁️ EC2

```
cd ~/StudentRecordManagement
source venv/bin/activate
gunicorn --bind 127.0.0.1:8000 app:app
```

Open a **second** SSH window and run:

```
curl http://127.0.0.1:8000/health
```

Expected: `{"database":"connected","status":"ok"}`. Stop Gunicorn in the first window with `Ctrl+C`.

## 12. Create the systemd service ☁️ EC2

```
sudo nano /etc/systemd/system/studentapp.service
```

Paste:

```ini
[Unit]
Description=Student Record Management (Gunicorn)
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/StudentRecordManagement
ExecStart=/home/ubuntu/StudentRecordManagement/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

The app reads `.env` from its own folder, so no extra environment settings are needed here. Start it and enable it at boot:

```
sudo systemctl daemon-reload
sudo systemctl enable --now studentapp
sudo systemctl status studentapp --no-pager
```

You should see `active (running)`.

## 13. Configure Nginx ☁️ EC2

```
sudo nano /etc/nginx/sites-available/studentapp
```

Paste:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it, disable the default welcome site, test and restart:

```
sudo ln -s /etc/nginx/sites-available/studentapp /etc/nginx/sites-enabled/studentapp
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

`nginx -t` must print `syntax is ok` and `test is successful`.

## 14. Open the website

In your Windows browser go to:

```
http://YOUR_EC2_PUBLIC_IP
```

Use **http**, not https (no certificate is configured in this basic setup, so some browsers may try https first; type `http://` explicitly). The dashboard should load. Also check `http://YOUR_EC2_PUBLIC_IP/health`.

## 15. Verify the data is stored in RDS ☁️ EC2 → 🗄️ RDS

1. In the browser, add a student with a recognizable roll number, for example `AWS001`.
2. On EC2, query RDS directly:

```
mysql -h YOUR_RDS_ENDPOINT -u student_app -p -e "SELECT roll_number, full_name, created_at FROM student_management.students ORDER BY id DESC LIMIT 5;"
```

   You should see `AWS001`.
3. Restart the application and reload the page; the student is still there:

```
sudo systemctl restart studentapp
```

4. Optional: reboot the server (`sudo reboot`), wait 1-2 minutes, then reopen the site. It should come back by itself, with the **new** public IP if you stopped/started rather than rebooted. Reconnect through the console to see the current IP.
5. Run the full testing checklist from the README against the public IP.

Take screenshots of the EC2 instance, the RDS instance (showing *Public access: No*), both security groups and the working site for your assignment report.

## 16. Troubleshooting

**Where to look first**

```
sudo systemctl status studentapp --no-pager      # is the app running?
sudo journalctl -u studentapp -n 50 --no-pager   # application errors (Gunicorn/Flask logs)
sudo nginx -t                                    # Nginx config valid?
sudo tail -n 50 /var/log/nginx/error.log         # Nginx errors
curl http://127.0.0.1:8000/health                # does the app reach RDS?
```

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser: site can't be reached / times out | Port 80 not allowed, instance stopped, or wrong IP (it changed) | Check `ec2-web-sg` has HTTP 80; confirm the instance is Running and use its current public IPv4 address; make sure you typed `http://` |
| SSH timeout | Your IP changed | Edit the SSH rule in `ec2-web-sg` to **My IP** again |
| SSH `Permission denied (publickey)` | Wrong user or key | Use `ubuntu@...` and the correct `.pem` file |
| 502 Bad Gateway | Gunicorn is not running | `sudo systemctl status studentapp`, read `journalctl` output, fix, then `sudo systemctl restart studentapp` |
| "Database unavailable" page | Wrong `.env` values or RDS unreachable | Check the journal for the real error (below), fix `.env`, restart the service |
| `mysql` hangs on connect, or `2003 Can't connect` / timeout | `rds-mysql-sg` does not allow port 3306 from `ec2-web-sg`, or different VPC | Re-check the inbound rule source; both resources must be in the same VPC |
| `1045 Access denied for user` | Wrong password or user, or the user was not created | Re-check `.env`; as `admin` run `SELECT user, host FROM mysql.user;` and recreate the user |
| `1044` / `1142 command denied` | Missing privilege | Re-run the `GRANT` statement and `FLUSH PRIVILEGES;` |
| `1049 Unknown database` | `database.sql` was not run on RDS | Run step 8 again |
| `Unknown MySQL server host` / name not resolved | Typo in `DB_HOST` | Copy the endpoint again from the RDS console |
| `.env` change has no effect | Service still running with old settings | `sudo systemctl restart studentapp` |
| Pulling new code | Updating the app | `cd ~/StudentRecordManagement && git pull && source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart studentapp` |

If the `/health` page says connected but Gunicorn fails to start, `journalctl` will show a Python traceback; the last line names the problem.

## 17. Stop and delete everything when finished

Cleanup removes only the resources you created for this assignment. Do these in order, and check the Region first.

**Take a final backup of your data if you need it** (from EC2): `mysqldump -h YOUR_RDS_ENDPOINT -u admin -p student_management > backup.sql`

☐ **RDS → Databases → `student-db` → Actions → Delete.** Untick *Create final snapshot* (unless you want one) and *Retain automated backups*, tick the acknowledgement, type `delete me`, confirm. Wait until it disappears.
☐ **RDS → Snapshots**: delete any manual snapshots you made. **Automated backups**: check none are retained.
☐ **EC2 → Instances → `student-app-server` → Instance state → Terminate instance.** (*Stop* only pauses compute; the disk and the public IPv4 charge can continue.) Wait for *Terminated*.
☐ **EC2 → Volumes**: confirm no leftover volume remains.
☐ **EC2 → Elastic IPs**: confirm none exist (you did not create one). Release any you did.
☐ **EC2 → Security Groups**: delete `rds-mysql-sg` first, then `ec2-web-sg` (RDS depends on the first, EC2 on the second).
☐ **EC2 → Key Pairs**: delete `student-app-key` and delete the `.pem` file from your computer.
☐ **Billing → Bills** (the next day) and **Billing → Free Tier**: confirm no running usage. Remove the budget if you no longer need it.
☐ Do **not** delete the default VPC, default subnets or anything you did not create.

If you only want a pause between demos, you can *stop* the RDS instance (AWS restarts it automatically after about 7 days, and storage is still billed) and *stop* the EC2 instance; terminate/delete both when the assignment is over.
