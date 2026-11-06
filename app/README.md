# App folder

The Northside Gym site: Python (Flask), served by gunicorn behind Apache. To deploy it, follow [`../docs/build-guide.md`](../docs/build-guide.md); `../scripts/install-app.sh` does the server setup.

| File | What it is |
| --- | --- |
| `app.py` | Routes: register, login, logout, profile, check-in, `/health` |
| `templates/` | Register, login and profile pages |
| `schema.sql` | `plans` and `members` tables, 3 sample plans, and the `gym_app` database user (no password in the file) |
| `requirements.txt` | Python packages |
| `deploy/gym-app.env.example` | Settings template. The real file lives only at `/etc/gym-app.env` on each server |
| `deploy/gym-app.service` | systemd service running gunicorn on `127.0.0.1:8000` |
| `deploy/gym-proxy.conf` | Apache passes port 80 to gunicorn |
| `deploy/dynamodb-policy.json` | Instance-role policy: `PutItem` and `Query` on `gym-checkins` only |

`CHECKINS_TABLE` in the settings file switches DynamoDB on. Leave it empty in phase 1.
