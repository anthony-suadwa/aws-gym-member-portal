-- Northside Gym schema for RDS for PostgreSQL.
-- Run once as the master user (see docs/build-guide.md, step 4):
--   psql "host=<endpoint> dbname=gym user=dbadmin sslmode=require" -f app/schema.sql

CREATE TABLE IF NOT EXISTS plans (
    id            serial PRIMARY KEY,
    name          text NOT NULL UNIQUE,
    monthly_price numeric(6,2) NOT NULL,
    perks         text NOT NULL
);

CREATE TABLE IF NOT EXISTS members (
    id            serial PRIMARY KEY,
    full_name     text NOT NULL,
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,                 -- never the password itself
    plan_id       int  NOT NULL REFERENCES plans(id),
    joined_on     date NOT NULL DEFAULT current_date,
    renews_on     date NOT NULL DEFAULT (current_date + interval '1 month')::date
);

INSERT INTO plans (name, monthly_price, perks) VALUES
    ('Basic',    19.99, 'Gym floor, off-peak only'),
    ('Standard', 29.99, 'Gym floor any time, 4 classes a month'),
    ('Premium',  44.99, 'Unlimited classes, sauna, 1 PT session a month')
ON CONFLICT (name) DO NOTHING;

-- The app logs in as this least-privilege user, never as the master user.
-- It is created WITHOUT a password, so no password ever sits in this file or in Git.
-- Set one afterwards inside psql with:  \password gym_app
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gym_app') THEN
        CREATE ROLE gym_app LOGIN;
    END IF;
END $$;

GRANT SELECT ON plans TO gym_app;
GRANT SELECT, INSERT ON members TO gym_app;
GRANT USAGE ON SEQUENCE members_id_seq TO gym_app;
