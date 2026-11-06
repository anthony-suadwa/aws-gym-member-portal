# Test results

Run on: YYYY-MM-DD, region `eu-west-2`. How to run each test is in [build-guide.md](build-guide.md).

| # | Test | Expected | Result | Evidence |
| --- | --- | --- | --- | --- |
| T1 | Register a member | Profile shows name, plan, price, renewal date | | `10-profile` |
| T2 | Add a plan in the database, reload `/register` | New plan in the dropdown, no code change | | `11-dynamic-plans` |
| T3 | Wrong password | Generic "Email or password is incorrect" | | `12-login-refused` |
| T4 | Read `password_hash` as `dbadmin` | Hashes only | | `13-hashed-passwords` |
| T5 | `DELETE FROM members` as `gym_app` | Permission denied | | `14-least-privilege-db` |
| T6 | RDS connectivity settings | Not public; 5432 only from `gym-web-sg` | | `15-rds-not-public` |
| T7 | Refresh the profile repeatedly | Server name changes, still logged in | | `16-load-balanced.gif` |
| T8 | Stop the app on one server | That target unhealthy, site still up | | `17-one-server-down` |
| T9 | Check in three times | Three visits, newest first | | `21-checkins` |
| T10 | Check in through both servers | Both server names in "Recorded by" | | `22-both-servers` |
| T11 | `scan` from a web server | AccessDenied | | `23-least-privilege-iam` |

Write **Pass** only for tests you ran and saw yourself.
